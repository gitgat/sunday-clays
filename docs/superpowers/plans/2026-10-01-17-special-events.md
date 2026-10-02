# Special Events Implementation Plan (Sub-plan 17)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking. Implementers, including fix rounds, run on Sonnet. Every reviewer, re-reviewer and verifier runs on Opus. Each task gets one branch, one worktree and one PR **into `feat/special-events`**, never `main`. Implementers commit but never push or open PRs. The controller pushes, opens the PRs and merges them, in the waves below. Task 9 is an operator task the controller runs by hand; it has no branch and no PR.

**Goal:** Record the club's special shoots, starting with the Sunday 2026-09-20 "Three Clay Shoot" (a 3-bird shoot over 10 stations of 6 targets, 60 targets, 40 shooters), as Sundays with their own label and target total. A special Sunday counts **only as an appearance** (Sundays shot, streaks, years active, Big Year, attendance trophies, turnout, calendars). Its scores stay out of **every** score-based number (averages, PBs, field metrics, ratings, predictions, records, leaderboards, score trophies, score insights, Explorer and the odometer's clays).

**Architecture:** Migration `0008` adds `events.kind` (`regular` | `special`, default `regular`), `events.label` and `events.target_total` (default 50), lets `imports.kind` be `special`, and adds the staging table `import_special_events`. A special import is one small workbook (sheet "Special Event": label, date, station labels, targets per station, then name + hits per station). `ingest/special.py` parses it and recomputes every total; `domain/imports.py` stages it into the existing `import_score_rows` and `import_station_*` tables plus `import_special_events`, and previews it (`SpecialDiff`: label, target total, shooters, new names, possible duplicates, which import it replaces, and any weekly-workbook rows on that date). `domain/rebuild.py` puts the newest committed special import of each date into the live `events`/`rounds`/`station_*` tables with `kind = 'special'`, and leaves weekly-workbook rows on a special date out (reported as a data issue). The exclusion is made once, at the seam every score consumer already reads: `frames.load_rounds`, `load_events` and `load_station_hits` return **regular Sundays only**, and the raw-SQL readers that bypass them (`analytics/stations.py`, the achievements station frame, the insights station readiness count, `weather_effects`, `predictions`) filter `kind = 'regular'`. Appearance consumers switch to two new frames, `load_appearances` (one row per shooter per Sunday shot, special included) and `load_calendar` (every Sunday, special included, with `kind`, `label`, `target_total`), and `streaks()` learns the rule that a special Sunday extends a run and never breaks one. The API adds `kind`/`label`/`target_total` to the Sunday payloads and a `GET /api/shooters/{id}/special` list. The frontend tags the Sunday everywhere ("Special · 60"), shows its results and station grid, and the admin page imports, previews, commits and rolls back the new kind.

**Tech Stack:** Python 3.13 · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 · pandas · openpyxl · pytest · Postgres 17 · React 19 · TypeScript (strict) · TanStack Query v5 · React Router v7 · Tailwind v4 · openapi-fetch · ECharts · Vitest + Testing Library + MSW · Playwright.

**Spec:** The approved design (owner, 2026-10-01) is quoted below and is binding. The format, global constraints and lessons come from `docs/superpowers/plans/2026-10-01-15-insight-bumps.md` on `origin/feat/special-events`.

**Base:** `feat/special-events` @ `39da248`, cut from `origin/feat/insight-bumps`, **plus Plan 16 Task 1** (migration `0007_page_views`), which is merging now. **Pre-flight** (controller, before each wave): every Create target must not exist, every Modify target must exist, and every "replace" block must occur exactly once in the task's base. Task 1 must not start until Plan 16 T1 has merged into `feat/special-events`: this plan's migration is `0008` with `down_revision = "0007"`, and Task 1's schema-test blocks are written against Plan 16 T1's version of `test_schema_0001.py`. If that file differs from the block quoted in Task 1 Step 1, keep the same shape (one more `downgrade` step and one more `TABLES_0008` subtraction) and record the difference in the PR.

**Delivery:** Task branches are `task/17-<N>-<slug>`, cut from `feat/special-events` after the previous wave has merged. Every PR targets `feat/special-events`, and CI (`ci-ok`, which includes the full Playwright suite) must pass. Commits use the gitgat identity, which is already in the repo config. Every commit ends with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. An implementer on another model names its own model there instead. After Task 8, the owner previews the branch locally, Task 9 loads 2026-09-20 into that preview, and only when the owner says so does one PR take `feat/special-events` to `main` and Task 9 repeat the load on production.

## Approved design (owner, 2026-10-01)

Quoted from the design brief. Two passages are reworded so that no real person's name enters this repo: the weekly scores workbook's keeper is not named, and the owner's identity rulings are referenced by where they live instead of being copied (Task 9 reads them there).

> **Problem:** on Sunday 2026-09-20 the club held a "Three Clay Shoot": a 3-bird event over 10 stations of 6 targets each, 60 targets in all, with 40 shooters. That date is currently absent from the DB. The app assumes every round is 50 targets (score 0..50) everywhere.
>
> **Data model:** add an event kind, regular|special. A special event carries a label (e.g. "Three Clay Shoot" / "3-bird") and its own target total (60). Its rounds keep raw scores out of that total. Station layout and hits are stored as for normal events (10 stations × 6 targets).
>
> **Counting rule (binding):**
> - A special event counts ONLY as an APPEARANCE. That covers events attended, attendance streaks (it must not break a streak; it extends one), years active, Big Year, new_year/anniversary/attendance trophies (Events Attended, Iron Streak, ...), club turnout and head counts, attendance calendars, and the profile's events count.
> - It is EXCLUDED from every score-based stat: averages, medians, PBs, field median/adjusted/percentile/rank, the skill model/ratings/difficulty/predictions, leaderboards (except appearance-type metrics such as events), records, score trophies (round_score, comeback, mudder, condition and competition trophies, station trophies), insights about scores, Explorer score metrics, and lifetime clays thrown and broken on the odometer.
> - Audit every analytics consumer of rounds/events, and make the exclusion explicit and tested at the single source of truth where possible. A good shape: frames.load_rounds excludes special-event rounds, with a separate appearances frame that includes them, but find the real seams.
>
> **UI:** the event page shows the results with a "3-bird shoot · 60 targets" style label and the station grid. A shooter's history/rounds list shows the row tagged "Special · 60". The events list and calendar mark it. Copy rules apply: no he/she/his/her; positive-only for named shooters. Charts keep ChartFrame/explainers.
>
> **Ingest:** a new admin import kind, "special event", alongside the scores/stations workbooks. It goes through the same staging → preview → commit → rebuild flow, versioned and rollback-able. Input file: a small xlsx (or csv) with the event date, the label, targets per station, and rows of name + per-station hits. Totals are recomputed and the sheet's total column is verified (mismatch → finding). Names use the normal identity resolution (ALIASES and rules apply). The preview lists new names and possible duplicates.
>
> **Data handling:** the real-name source file lives outside the repo at `/Users/bryanmoran/code/sunday-clays/.superpowers/special-events/2026-09-20-three-clay.csv` (header `name,s1..s10,total`, names as "First Last"). The plan must include a final operator task: convert that CSV to the import format WITHOUT committing it; apply the owner's identity rulings as alias_name rules before commit (*three rulings that map a sheet spelling to an existing shooter, and four names that are new shooters: they are listed in the private `README.md` next to that CSV and are deliberately not copied here*); load it into the local preview first, and into production only after the owner OKs; fixtures and tests use invented names only.
>
> If the weekly scores workbook ever contains a date that is a special event, the preview flags it rather than silently merging.
>
> **Process rules:** strict TDD (failing test, run, FAIL, implement, PASS), with tests that catch mutations. Coverage stays ≥90% lines and branches. Migrations are expand-only and safe while the previous release runs. Golden fixture counts in existing tests must not change, because the fixture has no special events. Add a no-leak/exclusion test per consumer family. e2e runs at both viewports (390x844 and 1440x900). Task PRs target feat/special-events; commits use the gitgat identity.

## Global Constraints

**Owner rules (binding), verbatim:**

- App copy never uses he/she/his/her.
- Named-shooter text is positive or neutral only. Negatives appear only at the club or field level.
- No skill-rating ranking and no rivals or head-to-head.
- Real people's names never appear in the repo. Tests and docs use the invented names: `Ike Hadley` / `Hadley, Ike` (shooter 3), `Amy Ace`, `Bob Bee`, `Cal Cy`, `Pat Kim`, and the fixture pseudonyms already in `backend/tests/fixtures` and `frontend/e2e` (`Devlin, Sid`, `Kaplan, Noel`, `Abernathy, Preston`, …). This plan's special-event fixtures use only those.
- Every chart keeps Table, CSV, fullscreen and its explainer. This plan adds no chart; it adds one series to the attendance calendar and one explainer.
- The spreadsheet score is authoritative (here: the special sheet's station hits, whose sum is the score).

**Repo conventions:**

- Python `3.13`, Node `22` LTS and Postgres `17`, with `uv` (backend) and `pnpm` (frontend). This plan adds no package. Never edit `[project].dependencies`, `[dependency-groups]`, `uv.lock`, `dependencies`, `devDependencies` or `pnpm-lock.yaml`.
- Coverage floor is **90% lines AND 90% branches**, with backend and frontend measured separately. `ratchets/` is controller-only.
- Backend gates: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict src`. Frontend gates: `pnpm lint` (`eslint --max-warnings 0`), `pnpm typecheck` (which first regenerates the gitignored `src/api/schema.d.ts` with `pnpm gen:api`) and `pnpm exec prettier --check .`.
- **Strict TDD with evidence:** every production change starts from a failing test. Each implementer report pastes the RED output (the failing run) and then the GREEN output (the passing run) for every step pair. Reviewers re-run the task's new tests on the task's base to prove they fail there, and mutate one line of each new production function (flip a comparison, drop a filter) to prove a test catches it.
- Migrations are expand-only and compatible with the previous release (`api` runs `alembic upgrade head` on start). This plan's one migration is `0008_special_events`. Its rollback limit is written in its docstring (Decision 3).
- **Golden counts never change.** The committed fixtures hold no special Sunday, so every existing golden (`tests/golden/*.json`, the insights counts, the participation/scoring/station achievement goldens, the e2e counts such as "36 Sundays in 2026") must pass untouched. A task that needs a special Sunday uses the new `fx_special_*` world (Task 2) or a unit-test builder, never the shared fixtures.
- Routers are discovered (C2). A module `api/routes/<name>.py` needs a viewer, `admin_<name>.py` an admin. Never edit `api/app.py`. Every `features/<name>/mocks.ts` `handlers` export is merged into the shared MSW server, which errors on unhandled requests (`src/test/setup.ts`).
- Viewports: phone `390×844` and desktop `1440×900` are both first-class. Tap targets are at least 44 px, no page scrolls sideways, and the e2e runs at both sizes.
- Copy says "Sunday", never "event" (the word is fine in code and in the admin import kind), and never uses "class". A special Sunday is a "special shoot" in copy.
- The theme is dark only and uses the existing Tailwind tokens (`bg-elevated`, `bg-surface`, `bg-primary`, `text-text`, `text-text-muted`, `text-accent`, `border-outline-variant`, `border-accent`, `rounded-card`, `rounded-button`). Never hard-code a colour; chart colours come from `theme/tokens`.
- Stage files explicitly (`git add <paths>`). Never `git add -A`: the repo root can hold untracked workbooks. The real-name CSV and anything converted from it never enter any repo (Task 9).
- Every PR runs the full Playwright suite under the required `ci-ok`. A task that changes visible copy also updates the existing unit test and e2e that assert that copy, in the same task (lesson PF-1).
- Workflows stay at about 10 agents or fewer. Non-conflicting lanes run in parallel (the waves below).
- Actions budget: Pro included minutes plus the $75 Actions budget. If CI is blocked by billing, stop and tell the owner.

## Review Focus

Six inputs or conditions that the design implies but does not spell out, and that are most likely to bite a person using this. Each is pinned to tests in the task that owns the code.

1. **A 60-target score leaking into a 50-target number.** A 55 at the Three Clay Shoot is above every possible regular score, so one leak shows up as a new club record, a "perfect 50" miscount, a personal best, a rating jump or a 110% hit rate. Expected: every score consumer sees exactly what it saw before the special Sunday existed. Tests: Task 3 `test_special_world_frames_match_the_regular_world` (rounds, metrics, events, station hits, ratings) and one test per raw-SQL family; Task 4 `test_score_trophies_are_unchanged_by_the_special_sunday` and `test_only_appearance_insights_change`; Task 5 `test_score_routes_answer_exactly_as_without_the_special_sunday`.
2. **A shooter whose only Sunday is the special one.** Four of the 40 are new. Expected: they get a profile (0 scored rounds, 1 Sunday shot), they are in the directory and on the Sundays board, their profile, insights, calendar and odometer render with no `NaN`, no 500 and no "missed" squares, and they never appear on a score board. Tests: Task 2 `test_profiles_count_the_special_sunday_as_an_event_but_not_a_round`; Task 5 `test_a_special_only_shooter_has_a_working_profile`; Task 6 `ProfileCharts.test.tsx` "a shooter with only a special shoot still gets a calendar".
3. **Streaks across a special Sunday.** Expected: a special Sunday extends the run of everyone who came, never breaks the run of anyone who did not, and does not end a "current" run when it is the latest Sunday. Tests: Task 3 `test_held_streaks.py` (four cases); Task 4 the Iron Streak and `pf.attendance-streak` cases; Task 5 `test_odometer_counts_the_special_sunday`.
4. **The weekly workbook also has rows on the special date.** Expected: the scores preview warns (`special_event_date`), the special preview warns (`regular_scores_on_special_date`), the rebuild keeps the special Sunday and reports `special_event_date_conflict`, and rolling the special import back brings the weekly rows back. Tests: Task 1 `test_regular_rows_on_the_special_date_are_flagged_in_both_previews`; Task 2 `test_weekly_rows_on_a_special_date_are_left_out_and_come_back_on_rollback`.
5. **A corrected re-upload.** Expected: the preview says which live import it replaces, committing it replaces the Sunday (label, scores, stations), rolling it back restores the earlier upload, and rolling that back too removes the Sunday. Tests: Task 1 `test_preview_says_which_live_import_it_replaces`; Task 2 `test_a_newer_special_import_replaces_the_older_one_and_rollback_restores_it`.
6. **Names in another order or spelling.** The source sheet writes "First Last"; the club's records are "Last, First"; three people appear under a different first name. Expected: Task 9 converts the order before upload, alias_name rules made before staging make those three known (the preview lists only the four genuinely new names), and the rebuild books their rounds to the existing shooters without creating new ones. Tests: Task 1 `test_an_alias_rule_makes_a_name_known_in_the_preview`; Task 2 `test_alias_rules_book_special_rows_to_the_existing_shooter`; Task 9 Step 5's preview check.

## Decisions

1. **Storage: special rounds live in `rounds`, marked by their event.** A special Sunday is an `events` row with `kind = 'special'`, `label` and `target_total`; its rounds are ordinary `rounds` rows (score 0..target_total) and its stations ordinary `station_layouts`/`station_hits` rows linked to them. That keeps one identity, one profile and one event page per Sunday. The exclusion is therefore a filter on the event's kind, applied at the frames seam and at each raw-SQL reader (Decision 6).
2. **Staging reuses the existing tables.** A special import (`imports.kind = 'special'`) stores its date, label and target total in the new `import_special_events` (PK `import_id`, `ON DELETE CASCADE`), its rows in `import_score_rows` (score = the recomputed total, status and gauge NULL) and its stations in `import_station_sheets`/`_layout`/`_hits` (one sheet named "Special Event"). `active_scores_import` and `active_station_sources` already filter on kind, so the weekly and station flows never see special rows.
3. **Migration `0008_special_events`, expand-only.** `events.kind text NOT NULL DEFAULT 'regular' CHECK IN ('regular','special')`, `events.label text NULL`, `events.target_total smallint NOT NULL DEFAULT 50`, `ck_imports_kind` widened to `('scores','stations','special')`, and the new staging table. The previous release inserts events without the new columns (defaults apply) and reads them by name, so it runs unchanged. **Rollback limit** (docstring): the previous release's `FileKind` has no `special`, so its import list fails once a special import exists, and its rebuild drops special Sundays; roll back only before a special import is uploaded, or after `DELETE FROM imports WHERE kind = 'special'` and a rebuild. Downgrade removes special imports, live special Sundays and the columns.
4. **The workbook format (xlsx only).** One sheet titled "Special Event" (case and spacing ignored): `A1 "Special event" | B1 label`, `A2 "Event date" | B2 date`, `A3 "Station" | B3… labels` (numbers or lettered labels such as 7A, then an optional "Total" header), `A4 "Targets" | B4… targets per station`, then one row per shooter from row 5: name, hits per station, optional total. The design allows csv; this plan takes **xlsx only**, so uploads keep the hardened zip-bomb/size checks, the `.xlsx` upload filter, the sha256 de-duplication and one parser. Task 9 converts the csv to this xlsx outside the repo. Detection order: scores sheet, then "Special Event" sheet, then station tabs.
5. **Parsing rules.** Unusable files raise `ParseError` with a plain message (no label, no date, no stations, a station label repeated, a target below 1, more than 30 stations, a label over 60 characters, no readable shooter row). Per row: a hit that is blank, not a whole number, negative or above that station's targets drops the row with an ERROR `special_hits_invalid`; a row with hits but no name is a WARNING `special_row_without_name`; a total cell that disagrees with the hits is a WARNING `special_total_mismatch` and the **recomputed** total is used. `validate_special` adds `non_sunday_date` and `name_repeated_in_sheet` (warnings, rows kept), as the station checks do.
6. **The seams (one filter each, tested per family).** Score-only: `frames.load_rounds`, `load_events`, `load_station_hits` (`WHERE e.kind = 'regular'`); `analytics/stations.py _FRAME_SQL`; `achievements/context.py _STATION_SQL`; `insights/store.py _STATION_SUNDAYS_SQL`; `weather_effects._WEATHER_EVENTS_SQL`; `predictions._scored_events`. Everything that reads those frames (s10 metrics, s30 skill and difficulty, s50 score/competition/condition/station trophies, s60 score insights, leaderboards' score metrics, records' score lists, Explorer, club distribution and first rounds, profile stats/PBs/splits/rating, predictions, weather pages, station pages, race and points) is covered by the seam. New appearance frames: `load_appearances` (shooter_id, event_date, kind, round_type, display_name, shooter_status, name_key, held; one row per shooter per Sunday shot) and `load_calendar` (every `events` row with event metrics and weather, plus `kind`, `label`, `target_total`). Special-only frames for display: `load_special_rounds`, `load_special_station_hits`.
7. **Appearance consumers switched in this plan.** `shooter_profiles.n_events/first_event/last_event` (rebuild; `n_rounds` counts regular rounds only); the profile odometer's Sundays, years active, favourite month and current/longest streak; the directory's Sundays; Events Attended, Years Active, Big Year, Iron Streak, New Year, the anniversaries, Welcome Back, Four Seasons and Perfect Month trophies; `pf.attendance-streak`, `rec.streak-chase` (attendance variant) and its proof rows, `pf.sunday-milestone` (Sunday counts), `pf.next-trophy` (progress) and `pf.shooter-anniversary` (its Sunday count); the Sundays leaderboard (`metric=events`, without a gauge filter); the records page's "Most Sundays" and "Longest runs"; the club summary's Sundays, held Sundays, shooters, shooters-by-status and average head count; the club attendance list; newcomer cohorts; the club trends' Sundays held, head counts and unique shooters, and the month profile's Sundays and head counts; Year in Review's Sundays held, shooters, newcomers, busiest Sunday, month Sundays and each shooter's Sundays and attendance rank; the club insights `cl.turnout-trend` (head counts), `cl.year-wrap` (Sundays held, busiest Sunday and its head count, first-timers) and `cl.newcomers` (cohorts over Sundays shot, matching the `/club` "new" chart it links to), where a special Sunday's turnout is its head count or, with none, the shooters on its sheet (the insights' existing `head_count or n` rule); the insight feeds' reference Sunday and expiry (`api/routes/insights.py held_dates`) stay on **regular** held Sundays, like `InsightFrames.sundays` (Decision 12); the profile's next Sundays milestone; the events list, calendar and event page; the shooter attendance calendar and "Sundays shot per month".
8. **Deliberately left on regular Sundays** (flag for the owner at preview; each is a one-line follow-up if wanted): club regulars and lapsed (a share of held Sundays), guest conversion and parity, `pf.attendance-year`, `pf.months-in-row`, `pf.year-wrapped` (quote "Sundays with full results"), the Explorer's attendance and shooters metrics (they share filters such as gauge and weather with score rows), the weather page's turnout bands and the two insights told against them, `cl.rain-turnout` (wet against dry turnout) and `ev.rain-day`'s crowd comparison (a wet Sunday's turnout against earlier dry Sundays; a special shoot's crowd is not a weather-driven turnout), the Explorer `attendance` chart that `cl.turnout-trend` links to (so on a window holding a special Sunday that fact counts one more Sunday than its chart), `cl.year-wrap`'s round count (scored rounds), the records' biggest jumps (consecutive scored Sundays; a special Sunday in between does not break the pair), the rust/layoff measures (score-based), `/api/meta` counts and the time-window anchor `last_score_date` (they still see the special Sunday as a Sunday with results, which is what anchors the 8W window).
9. **"A special Sunday never breaks a streak; it extends one."** `streaks()` keeps one calendar of held Sundays, special ones included. Two attended dates are consecutive when no **regular** held Sunday lies between them, and a current run is still current when no regular held Sunday follows its last date. So a special Sunday adds one to the run of everyone who came, is skipped for everyone who did not, and a special latest Sunday does not end anyone's current run. Without a special Sunday this is exactly the old rule, so goldens are unchanged. The insights `held_run`/`longest_before` use the same rule through `InsightFrames.no_held_between`.
10. **New Year and Perfect Month with a special Sunday.** New Year goes to everyone at the year's first regular held Sunday **and** to everyone at a special Sunday earlier that year (each shooter once, at their earliest such Sunday), so a January special shoot never takes the trophy away from the regulars. Perfect Month still needs every regular held Sunday of the month attended; a special Sunday attended that month counts toward the three Sundays it needs, and missing one never costs it.
11. **Milestones reached on a special Sunday.** Sunday counts (`Day.k`, the "to go" count, Events Attended tiers) include special Sundays. An anchored `pf.sunday-milestone` insight fires only on the regular Sunday that is itself the milestone; a milestone reached exactly at a special Sunday is marked by its Events Attended trophy instead (insights never anchor on a special Sunday, Decision 12).
12. **Insights never anchor on a special Sunday.** `InsightFrames.sundays` stays the regular held Sundays, so the special Sunday has no Sunday-page insights, no recap and no picks, and trophies dated on it are shown in the Trophy Room and Trophy Case but not as `pf.trophy-rare` news (the engine's existing out-of-scope guard drops them).
13. **Weekly rows on a special date.** The special import owns its date. At rebuild the weekly workbook's rows on that date are left out and a warning data issue `special_event_date_conflict` (`{rows, special_import_id}`) is written; its attendance head count still applies. The scores preview flags such rows with `special_event_date`, and the special preview counts them (`regular_rows_on_date`) with `regular_scores_on_special_date`.
14. **Versioning.** Per date, the newest committed special import is live (`committed_at desc, id desc`), like station sheets. A newer upload for the same date replaces it on commit; rolling the newer one back restores the older; rolling back the last one removes the Sunday. The preview's `replaces_import` names the live import a commit would replace.
15. **Identity.** Special rows go through the same `identity_key(name_key(raw), date)` keys and the same `resolve_shooter` as weekly rows. In addition, a key that appears on a special sheet and has an active `alias_name` rule is booked to that rule's shooter (newest rule wins, then merges apply), so an operator can map a sheet spelling to an existing shooter **before** commit without a merge. Weekly rows keep today's behaviour (alias_name rules still only steer station matching for them). The special preview's new names are the keys `identity_resolver` cannot place (rules, then aliases, then merges), with the same possible-duplicate hints as the scores preview (shared `_name_hints`).
16. **Round type of a special Sunday.** `sporting` with source `none` (owner rule: not super sporting ⇒ sporting), unless a `round_type_override` rule says otherwise. A round-type filter therefore keeps or hides it like any sporting Sunday.
17. **Rule targeting.** `score_override` and `hide_round` rules can target special rows (they are keyed by date, name key and ordinal like weekly rows). `Score` stays `0..50`, so an override above 50 is not possible; a corrected special sheet is the way to fix a special score.
18. **API shape.** `EventSummaryOut`, `EventDetailOut` and `AttendanceOut` gain `kind: Literal["regular","special"] = "regular"`, `label: str | None = None`, `target_total: int = 50` (defaults, so they are optional in the generated TS types and existing mocks stay valid). A special Sunday's `results` are its rounds with every metric `null`, `is_best_round: true` and `event_rank: null` (no ranking at a special shoot); `stations` is its station grid; `vs_prev` is `null`; `notables` lists first-timers only. `GET /api/shooters/{id}/rounds` stays regular-only (it feeds score charts). New `GET /api/shooters/{id}/special` → `[{round_id, event_date, label, target_total, score}]`, oldest first.
19. **Where the history row lives.** The profile gets a "Special shoots" card (an `events` feature `profileSection`, `bare`, rendered only when the shooter has one) listing each special Sunday with its date, label, the tag "Special · 60" and the score, linking to the Sunday. The attendance calendar draws an attended special Sunday as an accent-ringed square (series "Special", not on the score colour scale) and never draws a special Sunday as "missed"; "Sundays shot per month" counts it.
20. **The event page.** Header line "Three Clay Shoot · Special · 60 targets". A note explains the counting rule in neutral words. "This Sunday" shows Shooters, Targets and Stations (no median, top or difficulty). The results table is shooter and score ("Score (of 60)"), best first, no rank or rating columns. The station grid is the existing `StationHeatmap`. Weather stays; "vs previous Sunday" is hidden. The payload lists first-timers in `notables`, but the page shows none: `NotablesCard` leaves first-timers to the Sunday insights (Plan 12), and a special Sunday gets no insights (Decision 12). Flag this at preview.
21. **The events list and calendar.** A special Sunday reads "Three Clay Shoot · Special · 60 · 40 shooters" in the list. In the calendar it is an accent-bordered square labelled "Sep 20, 2026 — Three Clay Shoot, special shoot, 40 shooters", with a "Special shoot" legend entry.
22. **Admin.** The kind label is "Special shoot workbook". The diff card shows the Sunday, name, targets and station count, shooters, what it replaces, the weekly-rows warning, new names and possible duplicates. The upload hint reads "The kind (scores, stations or a special shoot) is detected from the workbook itself." The input keeps its label "Workbook (.xlsx)" (e2e uses it).
23. **The `fx_special` world.** Task 2 adds a session-scoped database built exactly like `fx_engine` plus one committed special import: 2026-09-20 (a Sunday the fixture does not have), "Three Clay Shoot", 10 stations × 6, rows `Hadley, Ike 55`, `Kaplan, Noel 51`, `Devlin, Sid 48`, `Abernathy, Preston 44` (all fixture shooters who shot 2026-09-13 and 2026-09-27) and the new `Kim, Pat 39`. Every no-leak test compares a consumer's output in this world with `fx_*`. It costs one more fixture build per backend run (about as long as `fx_engine`'s); the memo is keyed by database name, and tests still `clear_cache()` between worlds.
24. **e2e.** The special Sunday cannot be in the shared seed (golden counts), so the e2e is `special-events.admin-mutations.spec.ts`, matched by the existing `admin-mutations` project (`testMatch: /admin-mutations\.spec\.ts/` is unanchored and the read-only projects ignore the same pattern). It uploads, previews and commits a fixture workbook, checks the pages at 390×844 and at 1440×900 with `page.setViewportSize`, checks the API for unchanged score numbers and the extended streak, and rolls back in `finally`. `playwright.config.ts` is not edited (C10).
25. **Commit trailer.** Commands carry `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; an implementer on another model names its own model.
26. **Owner-preview notes.** Flag at preview: Decision 8's list (including the one-Sunday difference between `cl.turnout-trend` and its Explorer chart); no first-timers shown on the special Sunday's page (Decision 20); the csv path being an operator conversion (Decision 4); the special Sunday showing no Sunday-page insights (Decision 12); `last_score_date` still anchoring on a special Sunday if one is ever the latest (Decision 8).
27. **Operator note (parked).** After a rollback of a special import, a re-upload's preview lists the earlier new names as known, because the first rebuild already created their shooters and aliases (weekly imports behave the same). Compare the new names against the earlier list rather than expecting the original count.

## File map

| File | Task | Responsibility |
|---|---|---|
| `backend/src/sunday_clays/ingest/types.py` | 1 | `FileKind.SPECIAL`, `SpecialRow`, `SpecialParse` |
| `backend/src/sunday_clays/ingest/workbook.py` | 1 | `SPECIAL_SHEET`, detection order, unknown-kind message |
| `backend/src/sunday_clays/ingest/special.py` (new) | 1 | The special-sheet parser |
| `backend/src/sunday_clays/ingest/validate.py`, `ingest/__init__.py` | 1 | `validate_special`, dispatch |
| `backend/migrations/versions/0008_special_events.py` (new) | 1 | Event kind/label/target total, `imports.kind`, `import_special_events` |
| `backend/src/sunday_clays/models/live.py`, `models/staging.py`, `models/__init__.py` | 1 | ORM columns and `ImportSpecialEvent` |
| `backend/src/sunday_clays/domain/schemas.py` | 1 | `SpecialDiff` |
| `backend/src/sunday_clays/domain/imports.py` | 1, 2 | T1: staging, preview, `active_special_sources`, `_name_hints`, scores-preview flag. T2: scores-preview station findings skip special sheets |
| `backend/tests/conftest.py` | 1, 2 | T1: `special_workbook`. T2: the `fx_special_*` world |
| `backend/src/sunday_clays/domain/identity.py` | 2 | `alias_rule_targets` |
| `backend/src/sunday_clays/domain/rebuild.py` | 2 | Special Sundays into the live tables |
| `backend/src/sunday_clays/analytics/frames.py` | 3 | Regular-only score frames; `load_calendar`, `load_appearances`, `load_special_rounds`, `load_special_station_hits`, `appearances_from_rounds`, `calendar_from_events` |
| `backend/src/sunday_clays/analytics/streaks.py` | 3 | The special-Sunday streak rule |
| `backend/src/sunday_clays/analytics/{stations,weather_effects,predictions}.py`, `analytics/insights/store.py` | 3 | `kind = 'regular'` in raw SQL |
| `backend/src/sunday_clays/analytics/achievements/{context,participation}.py` | 3 (SQL), 4 | T3: station SQL filter. T4: appearances, calendar, attendance trophies |
| `backend/src/sunday_clays/analytics/insights/{context,attendance,milestones,records,anchors,trophies,club,community}.py`, `analytics/steps/s60_insights.py` | 4 | Appearance-aware insights, club turnout and newcomers |
| `backend/src/sunday_clays/api/routes/{events,shooters,shooter_insights,club,club_insights,insights}.py` | 5 | Sunday payloads, odometer, `/special`, club turnout, insight feeds on regular Sundays |
| `backend/src/sunday_clays/analytics/{leaderboards,records,yir,club_insights,profile}.py` | 5 | Appearance metrics |
| `frontend/src/features/events/**` | 6 | List, calendar, event page, "Special shoots" card, explainer |
| `frontend/src/features/shooters/{api.ts,charts.ts,explainers.ts,components/ProfileCharts.tsx}`, `frontend/src/components/charts/builders/sundayCalendar.ts` | 6 | Attendance calendar and months view |
| `frontend/src/features/admin/**` | 1, 7 | T1: diff types pinned so the widened union compiles. T7: special import preview and copy |
| `frontend/e2e/special-events.admin-mutations.spec.ts`, `frontend/e2e/fixtures/special_2026-09-20.xlsx` | 8 | End to end at both viewports |
| (outside every repo) | 9 | Convert, alias, load the real 2026-09-20 sheet |

## Waves

Tasks in one wave touch disjoint files and can run in parallel lanes. A wave starts once every PR of the waves before it has merged into `feat/special-events`.

| Wave | Tasks (parallel) | Needs |
|---|---|---|
| 1 | Task 1 | Plan 16 T1 merged (`0007`) |
| 2 | Task 2 | Task 1 (staging, `SpecialSource`, models) |
| 3 | Task 3 | Task 2 (the `fx_special` world) |
| 4 | Task 4 ∥ Task 5 | Task 3 (frames). Task 4 is `analytics/achievements/*`, `analytics/insights/*`, `steps/s60_insights.py` and their tests; Task 5 is `api/routes/*`, `analytics/{leaderboards,records,yir,club_insights,profile}.py` and their tests |
| 5 | Task 6 ∥ Task 7 | Tasks 1 and 5 (`pnpm gen:api`). Task 6 is `features/events`, `features/shooters`, `components/charts/builders/sundayCalendar.ts`; Task 7 is `features/admin` |
| 6 | Task 8 | Tasks 1–7 |
| 7 | Task 9 (operator) | Task 8 merged; owner preview |

## Running the e2e stack (Tasks 6, 7 and 8)

From the worktree root, build and start a stack from the branch on its own port, then run Playwright against it:

```bash
VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh   # once per worktree
E2E_PORT=18080 IMAGE_TAG=task17 docker compose -p task17 -f compose.yaml -f compose.test.yaml build
E2E_PORT=18080 IMAGE_TAG=task17 docker compose -p task17 -f compose.yaml -f compose.test.yaml up -d --wait
cd frontend && pnpm exec playwright install chromium
E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test <specs>
```

Afterwards, run `docker compose -p task17 -f compose.yaml -f compose.test.yaml down -v`.

---

### Task 1: The special-event workbook, migration 0008, staging and preview

Everything on the import side: the parser, the schema, and staging a special import with its preview. Nothing reaches the live tables yet (Task 2).

**Files:**
- Modify: `backend/src/sunday_clays/ingest/types.py`, `ingest/workbook.py`, `ingest/validate.py`, `ingest/__init__.py`
- Create: `backend/src/sunday_clays/ingest/special.py`
- Create: `backend/migrations/versions/0008_special_events.py`
- Modify: `backend/src/sunday_clays/models/live.py`, `models/staging.py`, `models/__init__.py`
- Modify: `backend/src/sunday_clays/domain/schemas.py`, `domain/imports.py`
- Create: `backend/tests/unit/ingest/builders_special.py`, `backend/tests/unit/ingest/test_special.py`
- Modify: `backend/tests/unit/ingest/test_workbook.py`, `backend/tests/unit/ingest/test_parse_upload.py`
- Modify: `backend/tests/integration/models/test_schema_0001.py`
- Modify: `backend/tests/conftest.py` (append the `special_workbook` fixture)
- Create: `backend/tests/integration/domain/test_stage_special.py`
- Modify: `backend/tests/integration/api/test_admin_imports_api.py`
- Modify: `frontend/src/features/admin/api.ts`, `frontend/src/features/admin/components/DiffSummary.tsx`, `frontend/src/features/admin/components/DiffSummary.test.tsx` (Step 12a: keep the admin page compiling once the preview union widens)

**Interfaces:**
- Consumes: `ingest.workbook.{LoadedWorkbook, find_sheet, coerce_date, coerce_int, is_blank, name_text, normalize_label}`, `ingest.names.{clean_display_name, name_key, identity_key}`, `station_label.{parse_label, label_number}`, `domain.identity.identity_resolver`, `domain.diff.{representative_names, possible_duplicate_pairs, StagedScore}`, the fixtures `session`, `admin_client`, `scratch_engine`, `seed_live_round`, `scores_workbook`, `mark_committed`.
- Produces (Tasks 2, 7, 8 and 9 rely on these):
  - `FileKind.SPECIAL = "special"`; `SpecialRow(row_number, raw_name, hits: tuple[tuple[str, int], ...])` with `.total`; `SpecialParse(event_date, label, layout, rows, findings)` with `.target_total` and `kind = FileKind.SPECIAL`; `ParsedUpload = ScoresParse | StationsParse | SpecialParse`.
  - `ingest.workbook.SPECIAL_SHEET = "Special Event"`; `ingest.special.parse_special(lw) -> SpecialParse`; `ingest.validate.validate_special(p) -> tuple[Finding, ...]`.
  - Finding codes `special_hits_invalid` (ERROR), `special_row_without_name`, `special_total_mismatch`, `regular_scores_on_special_date`, `special_event_date` (WARNING).
  - Models: `Event.kind: str` (default `'regular'`), `Event.label: str | None`, `Event.target_total: int` (default 50); `ImportSpecialEvent(import_id, event_date, label, target_total)`.
  - `domain.schemas.SpecialDiff(event_date, label, target_total, stations: list[str], n_shooters, replaces_import: int | None, regular_rows_on_date, new_names, possible_duplicates)`; `ImportPreview.diff: ScoresDiff | StationsDiff | SpecialDiff`.
  - `domain.imports.SpecialSource(import_id, sheet_id, label, target_total)`; `active_special_sources(session) -> dict[date, SpecialSource]`.
  - Root fixture `special_workbook(entries=..., *, event_date=date(2026, 9, 20), label="Three Clay Shoot", stations=1..10, targets=(6,)*10, total=True) -> bytes`.

- [ ] **Step 1: Write the failing parser tests**

Create `backend/tests/unit/ingest/builders_special.py`:

```python
"""Synthetic special-event sheets (test utility for Plan 17 Task 1)."""

from collections.abc import Sequence
from datetime import date

from .builders import SheetRows

SPECIAL_SUNDAY = date(2026, 9, 20)
LABEL = "Three Clay Shoot"
STATIONS = tuple(range(1, 11))
TARGETS = (6,) * 10
HADLEY = ["Hadley, Ike", 6, 5, 6, 4, 6, 5, 6, 6, 5, 6]  # 55
DEVLIN = ["Devlin, Sid", 5, 5, 4, 5, 5, 4, 5, 5, 5, 5]  # 48


def special_sheet(
    entries: SheetRows = (HADLEY, DEVLIN),
    *,
    label: object = LABEL,
    event_date: object = SPECIAL_SUNDAY,
    stations: Sequence[object] = STATIONS,
    targets: Sequence[object] = TARGETS,
    total: bool = True,
) -> list[list[object]]:
    """Rows of a "Special Event" sheet. With `total`, a row of exactly name + one int per station
    gets its correct total appended; a longer row keeps the total it was given."""
    rows: list[list[object]] = [
        ["Special event", label],
        ["Event date", event_date],
        ["Station", *stations, *(["Total"] if total else [])],
        ["Targets", *targets],
    ]
    for entry in entries:
        cells = list(entry)
        hits = cells[1:]
        if total and len(hits) == len(stations) and all(type(v) is int for v in hits):
            cells.append(sum(hits))  # type: ignore[arg-type]
        rows.append(cells)
    return rows
```

Create `backend/tests/unit/ingest/test_special.py`:

```python
"""The special-event sheet parser (Plan 17 Task 1)."""

from datetime import date

import pytest

from sunday_clays.ingest import parse_upload
from sunday_clays.ingest.special import (
    BAD_TARGETS,
    LABEL_TOO_LONG,
    MISSING_DATE,
    MISSING_LABEL,
    NO_ROWS,
    NO_STATIONS,
    TOO_MANY_STATIONS,
    parse_special,
)
from sunday_clays.ingest.types import FileKind, ParseError, Severity, SpecialParse
from sunday_clays.ingest.workbook import detect_kind

from .builders import loaded_workbook, workbook_bytes
from .builders_scores import SUNDAY, scores_sheets
from .builders_special import DEVLIN, HADLEY, LABEL, SPECIAL_SUNDAY, special_sheet

SHEET = "Special Event"


def parse(rows: list[list[object]]) -> SpecialParse:
    return parse_special(loaded_workbook({SHEET: rows}))


def test_parses_the_label_date_layout_and_rows() -> None:
    parsed = parse(special_sheet())

    assert parsed.label == LABEL
    assert parsed.event_date == SPECIAL_SUNDAY
    assert [e.label for e in parsed.layout] == [str(n) for n in range(1, 11)]
    assert [e.station_no for e in parsed.layout] == list(range(1, 11))
    assert {e.target_count for e in parsed.layout} == {6}
    assert parsed.target_total == 60
    assert [(r.row_number, r.raw_name, r.total) for r in parsed.rows] == [
        (5, "Hadley, Ike", 55),
        (6, "Devlin, Sid", 48),
    ]
    assert parsed.rows[0].hits[:2] == (("1", 6), ("2", 5))
    assert parsed.findings == ()
    assert parsed.kind is FileKind.SPECIAL


def test_detects_the_special_sheet_ignoring_case_and_spacing() -> None:
    assert detect_kind(loaded_workbook({" special   EVENT": special_sheet()})) is FileKind.SPECIAL


def test_a_scores_sheet_still_wins_over_a_special_sheet() -> None:
    both = loaded_workbook({**scores_sheets(), SHEET: special_sheet()})
    assert detect_kind(both) is FileKind.SCORES


def test_lettered_stations_keep_their_label_and_sort_number() -> None:
    rows = special_sheet(
        [["Hadley, Ike", 5, 6, 4, 3]], stations=(1, 2, "7a", 8), targets=(6, 6, 6, 6)
    )
    parsed = parse(rows)

    assert [(e.label, e.station_no) for e in parsed.layout] == [
        ("1", 1),
        ("2", 2),
        ("7A", 7),
        ("8", 8),
    ]
    assert parsed.target_total == 24
    assert parsed.rows[0].hits[2] == ("7A", 4)


def test_a_wrong_total_is_reported_and_the_station_sum_is_used() -> None:
    parsed = parse(special_sheet([[*HADLEY, 50], DEVLIN]))

    assert [r.total for r in parsed.rows] == [55, 48]
    (finding,) = parsed.findings
    assert (finding.code, finding.severity, finding.row, finding.name) == (
        "special_total_mismatch",
        Severity.WARNING,
        5,
        "Hadley, Ike",
    )
    assert finding.message == "The total column says 50 but the stations add up to 55; 55 is used"
    assert (finding.sheet, finding.event_date) == (SHEET, SPECIAL_SUNDAY)


def test_a_blank_total_or_no_total_column_is_not_reported() -> None:
    assert parse(special_sheet([[*HADLEY, None]])).findings == ()
    no_total = parse(special_sheet([HADLEY], total=False))
    assert no_total.findings == ()
    assert no_total.rows[0].total == 55


@pytest.mark.parametrize(
    ("value", "shown"),
    [(7, "7"), (-1, "-1"), (None, "nothing"), ("x", "x"), (4.5, "4.5")],
)
def test_a_hit_that_is_not_a_count_up_to_the_targets_drops_the_row(
    value: object, shown: str
) -> None:
    bad = ["Devlin, Sid", 5, 5, value, 5, 5, 4, 5, 5, 5, 5, 48]
    parsed = parse(special_sheet([HADLEY, bad]))

    assert [r.raw_name for r in parsed.rows] == ["Hadley, Ike"]
    (finding,) = parsed.findings
    assert (finding.code, finding.severity, finding.row, finding.name) == (
        "special_hits_invalid",
        Severity.ERROR,
        6,
        "Devlin, Sid",
    )
    assert finding.message == (
        f"Station 3 has {shown}, not a hit count from 0 to 6; the row is left out"
    )


def test_hits_without_a_name_are_reported_and_blank_rows_are_skipped() -> None:
    parsed = parse(special_sheet([HADLEY, [], [None, 5, 5], DEVLIN]))

    assert [r.raw_name for r in parsed.rows] == ["Hadley, Ike", "Devlin, Sid"]
    (finding,) = parsed.findings
    assert (finding.code, finding.severity, finding.row) == (
        "special_row_without_name",
        Severity.WARNING,
        7,
    )
    assert finding.message == "This row has hits but no name; it is left out"


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (special_sheet(label=None), MISSING_LABEL),
        (special_sheet(label="   "), MISSING_LABEL),
        (special_sheet(label="x" * 61), LABEL_TOO_LONG),
        (special_sheet(event_date=None), MISSING_DATE),
        (special_sheet(event_date="soon"), MISSING_DATE),
        (special_sheet(stations=(), targets=()), NO_STATIONS),
        (special_sheet([HADLEY], stations=("Stn", 2), targets=(6, 6)), "Row 3 has 'Stn' where a station number belongs"),
        (special_sheet([HADLEY], stations=(1, 1), targets=(6, 6)), "Station 1 appears twice in row 3"),
        (special_sheet([HADLEY], stations=(1, 2), targets=(6, 0)), BAD_TARGETS),
        (special_sheet([HADLEY], stations=(1, 2), targets=(6, None)), BAD_TARGETS),
        (special_sheet(stations=tuple(range(1, 32)), targets=(6,) * 31), TOO_MANY_STATIONS),
        (special_sheet([]), NO_ROWS),
    ],
    ids=[
        "no-label",
        "blank-label",
        "long-label",
        "no-date",
        "text-date",
        "no-stations",
        "not-a-station",
        "repeated-station",
        "zero-targets",
        "blank-targets",
        "31-stations",
        "no-rows",
    ],
)
def test_an_unusable_sheet_raises_a_plain_message(rows: list[list[object]], message: str) -> None:
    with pytest.raises(ParseError) as excinfo:
        parse(rows)
    assert str(excinfo.value) == message


def test_a_label_of_sixty_characters_and_thirty_stations_are_fine() -> None:
    thirty = tuple(range(1, 31))
    rows = special_sheet(
        [["Hadley, Ike", *([5] * 30)]], label="x" * 60, stations=thirty, targets=(6,) * 30
    )
    parsed = parse(rows)
    assert len(parsed.label) == 60
    assert len(parsed.layout) == 30
    assert parsed.rows[0].total == 150


def test_when_every_row_is_unreadable_the_message_names_the_first_problem() -> None:
    bad = ["Devlin, Sid", 9, 5, 4, 5, 5, 4, 5, 5, 5, 5]
    with pytest.raises(ParseError) as excinfo:
        parse(special_sheet([bad]))
    assert str(excinfo.value) == (
        f"{NO_ROWS}: Station 1 has 9, not a hit count from 0 to 6; the row is left out (row 5)"
    )


def test_a_missing_sheet_is_a_parse_error() -> None:
    with pytest.raises(ParseError, match='no "Special Event" sheet'):
        parse_special(loaded_workbook({"Other": [["x"]]}))


def test_parse_upload_dispatches_and_validates_a_special_workbook() -> None:
    monday = date(2026, 9, 21)
    parsed = parse_upload(workbook_bytes({SHEET: special_sheet([HADLEY, HADLEY], event_date=monday)}))

    assert isinstance(parsed, SpecialParse)
    assert [(f.code, f.severity, f.row) for f in parsed.findings] == [
        ("non_sunday_date", Severity.WARNING, None),
        ("name_repeated_in_sheet", Severity.WARNING, 5),
    ]
    assert parsed.findings[0].message == "2026-09-21 is a Monday, not a Sunday"
    assert parsed.findings[0].sheet == SHEET
    assert parsed.findings[1].message == "This name is on 2 rows of the sheet"
    assert len(parsed.rows) == 2  # kept: warnings never drop a row


def test_a_sunday_special_sheet_validates_clean() -> None:
    parsed = parse_upload(workbook_bytes({SHEET: special_sheet(event_date=SUNDAY)}))
    assert isinstance(parsed, SpecialParse)
    assert parsed.findings == ()
```

Two lines in the parametrize list are over 100 characters; Step 3's `ruff format` wraps them (no logic change).

In `backend/tests/unit/ingest/test_workbook.py`, replace

```python
    assert str(excinfo.value) == (
        "This doesn't look like a Sunday Clays scores or station workbook"
    )
```

with

```python
    assert str(excinfo.value) == (
        "This doesn't look like a Sunday Clays scores, station or special event workbook"
    )
```

In `backend/tests/unit/ingest/test_parse_upload.py`, replace

```python
            "This doesn't look like a Sunday Clays scores or station workbook",
```

with

```python
            "This doesn't look like a Sunday Clays scores, station or special event workbook",
```

and add, at the end of `FINDING_CASES` (before its closing `]`):

```python
    # validate_special and the special parser (Plan 17)
    ("special_total_mismatch", Severity.WARNING, {"Special Event": special_sheet([[*S_HADLEY, 1]])}),
    (
        "special_hits_invalid",
        Severity.ERROR,
        {"Special Event": special_sheet([S_HADLEY, ["Devlin, Sid", 9, 5, 4, 5, 5, 4, 5, 5, 5, 5]])},
    ),
    (
        "special_row_without_name",
        Severity.WARNING,
        {"Special Event": special_sheet([S_HADLEY, [None, 5]])},
    ),
```

then replace

```python
        f"{code}-{severity}-{'stations' if 'ALL SCORE DETAIL' not in sheets else 'scores'}"
```

with

```python
        f"{code}-{severity}-{_kind_id(sheets)}"
```

and add, just above `FINDING_CASES`, the import and helper:

```python
from .builders_special import HADLEY as S_HADLEY
from .builders_special import special_sheet


def _kind_id(sheets: Mapping[str, SheetRows]) -> str:
    if "ALL SCORE DETAIL" in sheets:
        return "scores"
    return "special" if "Special Event" in sheets else "stations"
```

(Move the two `from .builders_special import …` lines up into the module's import block if ruff's `I` rule asks; it does with `ruff check --fix`.)

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/unit/ingest/test_special.py tests/unit/ingest/test_workbook.py tests/unit/ingest/test_parse_upload.py`
Expected: FAIL at collection of `test_special.py` with `ModuleNotFoundError: No module named 'sunday_clays.ingest.special'`, and the two message assertions fail with the old text.

- [ ] **Step 3: Write the parser**

In `backend/src/sunday_clays/ingest/types.py`, replace

```python
class FileKind(StrEnum):
    SCORES = "scores"
    STATIONS = "stations"
```

with

```python
class FileKind(StrEnum):
    SCORES = "scores"
    STATIONS = "stations"
    SPECIAL = "special"  # Plan 17: one special Sunday with its own label and target total
```

and replace

```python
ParsedUpload = ScoresParse | StationsParse
```

with

```python
@dataclass(frozen=True)
class SpecialRow:
    """One shooter's row on a special-event sheet: (station label, hits) in layout order."""

    row_number: int
    raw_name: str
    hits: tuple[tuple[str, int], ...]

    @property
    def total(self) -> int:
        """The score: always recomputed from the stations, never read from a total cell."""
        return sum(hits for _, hits in self.hits)


@dataclass(frozen=True)
class SpecialParse:
    """A special event (Plan 17): one Sunday, its own name and target total, one round each."""

    event_date: date
    label: str
    layout: tuple[StationLayoutEntry, ...]
    rows: tuple[SpecialRow, ...]
    findings: tuple[Finding, ...]
    kind: ClassVar[FileKind] = FileKind.SPECIAL

    @property
    def target_total(self) -> int:
        return sum(entry.target_count for entry in self.layout)


ParsedUpload = ScoresParse | StationsParse | SpecialParse
```

In `backend/src/sunday_clays/ingest/workbook.py`, replace

```python
SCORES_SHEET = "ALL SCORE DETAIL"
UNREADABLE_MESSAGE = "This file could not be read as an Excel workbook"
TOO_LARGE_MESSAGE = "File is too large to process"
UNKNOWN_KIND_MESSAGE = "This doesn't look like a Sunday Clays scores or station workbook"
```

with

```python
SCORES_SHEET = "ALL SCORE DETAIL"
SPECIAL_SHEET = "Special Event"  # Plan 17: a special-event workbook's one sheet
UNREADABLE_MESSAGE = "This file could not be read as an Excel workbook"
TOO_LARGE_MESSAGE = "File is too large to process"
UNKNOWN_KIND_MESSAGE = (
    "This doesn't look like a Sunday Clays scores, station or special event workbook"
)
```

and replace

```python
def detect_kind(lw: LoadedWorkbook) -> FileKind:
    if find_sheet(lw.values, SCORES_SHEET) is not None:
        return FileKind.SCORES
    if any(is_station_sheet(sheet) for sheet in worksheets(lw.values)):
        return FileKind.STATIONS
    raise ParseError(UNKNOWN_KIND_MESSAGE)
```

with

```python
def detect_kind(lw: LoadedWorkbook) -> FileKind:
    """Scores sheet first, then the special-event sheet, then station tabs."""
    if find_sheet(lw.values, SCORES_SHEET) is not None:
        return FileKind.SCORES
    if find_sheet(lw.values, SPECIAL_SHEET) is not None:
        return FileKind.SPECIAL
    if any(is_station_sheet(sheet) for sheet in worksheets(lw.values)):
        return FileKind.STATIONS
    raise ParseError(UNKNOWN_KIND_MESSAGE)
```

Create `backend/src/sunday_clays/ingest/special.py`:

```python
"""Special-event workbooks (Plan 17): one sheet, one Sunday, one round per shooter.

The "Special Event" sheet (titles match ignoring case and spacing):

    A1 "Special event"  B1 the shoot's name, e.g. "Three Clay Shoot"
    A2 "Event date"     B2 the date
    A3 "Station"        B3... station labels (1, 2, ... or 7A), then optionally "Total"
    A4 "Targets"        B4... targets thrown at each station
    A5...               one shooter per row: name, hits per station, optionally the total

Every total is recomputed from the station hits; a total cell that disagrees is reported.
Pure module: no database, no I/O.
"""

from __future__ import annotations

from datetime import date

from openpyxl.worksheet.worksheet import Worksheet

from sunday_clays.ingest.names import clean_display_name
from sunday_clays.ingest.types import (
    Finding,
    ParseError,
    Severity,
    SpecialParse,
    SpecialRow,
    StationLayoutEntry,
)
from sunday_clays.ingest.workbook import (
    SPECIAL_SHEET,
    LoadedWorkbook,
    coerce_date,
    coerce_int,
    find_sheet,
    is_blank,
    name_text,
    normalize_label,
)
from sunday_clays.station_label import label_number, parse_label

LABEL_ROW, DATE_ROW, STATION_ROW, TARGET_ROW, FIRST_ENTRY_ROW = 1, 2, 3, 4, 5
VALUE_COLUMN = 2  # B: the label, the date and the first station
MAX_STATIONS = 30
MAX_LABEL_CHARS = 60
TOTAL_HEADER = "total"

MISSING_SHEET = f'The workbook has no "{SPECIAL_SHEET}" sheet'
MISSING_LABEL = 'Cell B1 needs the name of the special shoot, such as "Three Clay Shoot"'
LABEL_TOO_LONG = f"The special shoot's name in B1 is longer than {MAX_LABEL_CHARS} characters"
MISSING_DATE = "Cell B2 needs the date of the special shoot"
NO_STATIONS = "Row 3 needs station numbers from column B (1, 2, 3 or a label such as 7A)"
BAD_TARGETS = "Row 4 needs a target count of 1 or more under every station"
TOO_MANY_STATIONS = f"Row 3 has more than {MAX_STATIONS} stations"
NO_ROWS = "No shooter rows could be read from row 5 down"


def parse_special(lw: LoadedWorkbook) -> SpecialParse:
    """The special sheet as a SpecialParse; ParseError for anything that cannot be used."""
    sheet = find_sheet(lw.values, SPECIAL_SHEET)
    if sheet is None:
        raise ParseError(MISSING_SHEET)
    label = _label(sheet)
    event_date = coerce_date(sheet.cell(row=DATE_ROW, column=VALUE_COLUMN).value)
    if event_date is None:
        raise ParseError(MISSING_DATE)
    layout, total_column = _layout(sheet)
    findings: list[Finding] = []
    rows = [
        row
        for number in range(FIRST_ENTRY_ROW, sheet.max_row + 1)
        if (row := _row(sheet, number, layout, total_column, event_date, findings)) is not None
    ]
    if not rows:
        if findings:
            first = findings[0]
            raise ParseError(f"{NO_ROWS}: {first.message} (row {first.row})")
        raise ParseError(NO_ROWS)
    return SpecialParse(event_date, label, layout, tuple(rows), tuple(findings))


def _label(sheet: Worksheet) -> str:
    value = sheet.cell(row=LABEL_ROW, column=VALUE_COLUMN).value
    text = "" if is_blank(value) else clean_display_name(str(value))
    if not text:
        raise ParseError(MISSING_LABEL)
    if len(text) > MAX_LABEL_CHARS:
        raise ParseError(LABEL_TOO_LONG)
    return text


def _layout(sheet: Worksheet) -> tuple[tuple[StationLayoutEntry, ...], int | None]:
    """Station columns from B3 rightwards, up to a blank or a "Total" header (its column)."""
    entries: list[StationLayoutEntry] = []
    for column in range(VALUE_COLUMN, VALUE_COLUMN + MAX_STATIONS + 1):
        header = sheet.cell(row=STATION_ROW, column=column).value
        if is_blank(header):
            break
        if normalize_label(header) == TOTAL_HEADER:
            return _checked(entries), column
        label = parse_label(header)
        if label is None:
            raise ParseError(f"Row 3 has {header!r} where a station number belongs")
        if any(entry.label == label for entry in entries):
            raise ParseError(f"Station {label} appears twice in row 3")
        target = coerce_int(sheet.cell(row=TARGET_ROW, column=column).value)
        if target is None or target < 1:
            raise ParseError(BAD_TARGETS)
        entries.append(StationLayoutEntry(label_number(label), target, label))
    return _checked(entries), None


def _checked(entries: list[StationLayoutEntry]) -> tuple[StationLayoutEntry, ...]:
    if not entries:
        raise ParseError(NO_STATIONS)
    if len(entries) > MAX_STATIONS:
        raise ParseError(TOO_MANY_STATIONS)
    return tuple(entries)


def _shown(value: object) -> str:
    return "nothing" if is_blank(value) else str(value)


def _row(
    sheet: Worksheet,
    number: int,
    layout: tuple[StationLayoutEntry, ...],
    total_column: int | None,
    event_date: date,
    findings: list[Finding],
) -> SpecialRow | None:
    raw_name = name_text(sheet.cell(row=number, column=1).value)
    values = [
        sheet.cell(row=number, column=VALUE_COLUMN + i).value for i in range(len(layout))
    ]
    if raw_name is None:
        if not all(is_blank(value) for value in values):
            findings.append(
                Finding(
                    "special_row_without_name",
                    Severity.WARNING,
                    "This row has hits but no name; it is left out",
                    sheet=SPECIAL_SHEET,
                    row=number,
                    event_date=event_date,
                )
            )
        return None
    name = clean_display_name(raw_name)
    hits: list[tuple[str, int]] = []
    for entry, value in zip(layout, values, strict=True):
        count = coerce_int(value)
        if count is None or not 0 <= count <= entry.target_count:
            findings.append(
                Finding(
                    "special_hits_invalid",
                    Severity.ERROR,
                    f"Station {entry.label} has {_shown(value)}, not a hit count from 0 to "
                    f"{entry.target_count}; the row is left out",
                    sheet=SPECIAL_SHEET,
                    row=number,
                    event_date=event_date,
                    name=name,
                )
            )
            return None
        hits.append((entry.label, count))
    row = SpecialRow(number, raw_name, tuple(hits))
    if total_column is not None:
        given = sheet.cell(row=number, column=total_column).value
        if not is_blank(given) and coerce_int(given) != row.total:
            findings.append(
                Finding(
                    "special_total_mismatch",
                    Severity.WARNING,
                    f"The total column says {_shown(given)} but the stations add up to "
                    f"{row.total}; {row.total} is used",
                    sheet=SPECIAL_SHEET,
                    row=number,
                    event_date=event_date,
                    name=name,
                )
            )
    return row
```

In `backend/src/sunday_clays/ingest/validate.py`, replace

```python
from sunday_clays.ingest.types import (
    AttendanceRow,
    Finding,
    ScoreRow,
    ScoresParse,
    Severity,
    StationSheet,
    StationsParse,
)
from sunday_clays.ingest.workbook import SCORES_SHEET
```

with

```python
from sunday_clays.ingest.types import (
    AttendanceRow,
    Finding,
    ScoreRow,
    ScoresParse,
    Severity,
    SpecialParse,
    StationSheet,
    StationsParse,
)
from sunday_clays.ingest.workbook import SCORES_SHEET, SPECIAL_SHEET
```

and add after `validate_stations`:

```python
def validate_special(p: SpecialParse) -> tuple[Finding, ...]:
    """A special sheet's date and repeated names, as the station checks report them."""
    findings: list[Finding] = []
    if p.event_date.weekday() != _SUNDAY:
        findings.append(_non_sunday(p.event_date, sheet=SPECIAL_SHEET))
    repeats = Counter(name_key(row.raw_name) for row in p.rows)
    for row in p.rows:
        count = repeats.pop(name_key(row.raw_name), 0)
        if count >= 2:
            findings.append(
                Finding(
                    "name_repeated_in_sheet",
                    Severity.WARNING,
                    f"This name is on {count} rows of the sheet",
                    sheet=SPECIAL_SHEET,
                    row=row.row_number,
                    event_date=p.event_date,
                    name=clean_display_name(row.raw_name),
                )
            )
    return tuple(findings)
```

In `backend/src/sunday_clays/ingest/__init__.py`, replace

```python
from sunday_clays.ingest.scores import parse_scores
from sunday_clays.ingest.stations import parse_stations
from sunday_clays.ingest.types import FileKind, ParsedUpload, ParseError
from sunday_clays.ingest.validate import validate_scores, validate_stations
```

with

```python
from sunday_clays.ingest.scores import parse_scores
from sunday_clays.ingest.special import parse_special
from sunday_clays.ingest.stations import parse_stations
from sunday_clays.ingest.types import FileKind, ParsedUpload, ParseError
from sunday_clays.ingest.validate import validate_scores, validate_special, validate_stations
```

and replace

```python
    lw = load_workbook_bytes(data)
    if detect_kind(lw) is FileKind.SCORES:
        scores = parse_scores(lw)
        return replace(scores, findings=scores.findings + validate_scores(scores))
```

with

```python
    lw = load_workbook_bytes(data)
    kind = detect_kind(lw)
    if kind is FileKind.SCORES:
        scores = parse_scores(lw)
        return replace(scores, findings=scores.findings + validate_scores(scores))
    if kind is FileKind.SPECIAL:
        special = parse_special(lw)
        return replace(special, findings=special.findings + validate_special(special))
```

and change the module docstring's first line to `"""Workbook ingest: pure parsers for the Sunday Clays workbooks (Contract C3, Plan 17).`.

`domain/imports.py` dispatches on the parse type, and mypy now sees `SpecialParse` reach its `else` branch, so this step also adds the branch that Step 11 fills in. In `backend/src/sunday_clays/domain/imports.py`, replace

```python
    if isinstance(parsed, ScoresParse):
        _stage_scores(session, imp.id, parsed)
        diff, station_findings = _preview_scores(session, imp.id)
        requires_confirmation = bool(diff.events_removed) or diff.rows_removed > 0
    else:
```

with

```python
    if isinstance(parsed, ScoresParse):
        _stage_scores(session, imp.id, parsed)
        diff, station_findings = _preview_scores(session, imp.id)
        requires_confirmation = bool(diff.events_removed) or diff.rows_removed > 0
    elif isinstance(parsed, SpecialParse):
        raise ParseError("Special shoot imports are not ready yet")  # replaced in Step 11
    else:
```

and add `SpecialParse` to its `from sunday_clays.ingest.types import (...)` list and `ParseError` to the same import.

- [ ] **Step 4: Run them to verify they pass**

Run: `cd backend && uv run ruff format src tests && uv run ruff check --fix src tests && uv run pytest -q tests/unit/ingest`
Expected: all pass (the parametrized ids now read `…-special`).

- [ ] **Step 5: Write the failing migration and model tests**

In `backend/tests/integration/models/test_schema_0001.py`, replace (Plan 16 T1's block)

```python
    "page_views",  # 0007 (Plan 16)
    "page_view_attempts",  # 0007 (Plan 16)
    "page_view_rollups",  # 0007 (Plan 16)
    "page_kind_rollups",  # 0007 (Plan 16)
}
TABLES_0003 = {"insights", "insight_picks"}
TABLES_0006 = {"fist_bumps", "bump_attempts"}
TABLES_0007 = {"page_views", "page_view_attempts", "page_view_rollups", "page_kind_rollups"}
```

with

```python
    "page_views",  # 0007 (Plan 16)
    "page_view_attempts",  # 0007 (Plan 16)
    "page_view_rollups",  # 0007 (Plan 16)
    "page_kind_rollups",  # 0007 (Plan 16)
    "import_special_events",  # 0008 (Plan 17)
}
TABLES_0003 = {"insights", "insight_picks"}
TABLES_0006 = {"fist_bumps", "bump_attempts"}
TABLES_0007 = {"page_views", "page_view_attempts", "page_view_rollups", "page_kind_rollups"}
TABLES_0008 = {"import_special_events"}
```

and in `test_upgrade_downgrade_roundtrip` replace

```python
    _alembic(scratch_engine, "downgrade", "0006")  # 0007 drops only its four tables
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0007) | {"alembic_version"}
    later = TABLES_0006 | TABLES_0007
```

with

```python
    _alembic(scratch_engine, "downgrade", "0007")  # 0008 drops its table and the event kind
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0008) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0006")  # 0007 drops only its four tables
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0007 - TABLES_0008) | {"alembic_version"}
    later = TABLES_0006 | TABLES_0007 | TABLES_0008
```

Then append to the same file:

```python
EVENT_INSERT = (
    "INSERT INTO events (event_date, round_type, round_type_source, n_rounds, n_shooters,"
    " has_scores, has_stations, results_complete"
)


def test_0008_defaults_events_to_regular_and_stores_a_special_sunday(
    scratch_engine: Engine,
) -> None:
    _alembic(scratch_engine, "upgrade", "0007")
    with scratch_engine.begin() as conn:
        conn.execute(text(f"{EVENT_INSERT}) VALUES ('2026-09-13', 'sporting', 'none', 0, 0,"
                          " false, false, false)"))
    _alembic(scratch_engine, "upgrade", "head")
    with scratch_engine.begin() as conn:
        # the previous release writes no kind, label or target total
        conn.execute(text(f"{EVENT_INSERT}) VALUES ('2026-09-27', 'sporting', 'none', 0, 0,"
                          " false, false, false)"))
        conn.execute(text(f"{EVENT_INSERT}, kind, label, target_total) VALUES ('2026-09-20',"
                          " 'sporting', 'none', 0, 0, false, false, false, 'special',"
                          " 'Three Clay Shoot', 60)"))
        rows = conn.execute(
            text("SELECT event_date::text, kind, label, target_total FROM events ORDER BY 1")
        ).all()
    assert [tuple(r) for r in rows] == [
        ("2026-09-13", "regular", None, 50),
        ("2026-09-20", "special", "Three Clay Shoot", 60),
        ("2026-09-27", "regular", None, 50),
    ]
    with pytest.raises(IntegrityError, match="ck_events_kind"), scratch_engine.begin() as conn:
        conn.execute(text(f"{EVENT_INSERT}, kind) VALUES ('2026-10-04', 'sporting', 'none', 0,"
                          " 0, false, false, false, 'party')"))


def test_0008_downgrade_removes_special_imports_and_special_sundays(
    scratch_engine: Engine,
) -> None:
    _alembic(scratch_engine, "upgrade", "head")
    with scratch_engine.begin() as conn:
        conn.execute(text("INSERT INTO shooters (id, display_name) VALUES (1, 'Hadley, Ike')"))
        conn.execute(text("INSERT INTO imports (id, kind, filename, sha256, file_bytes, status)"
                          " VALUES (7, 'special', 's.xlsx', 'abc', 'x', 'committed')"))
        conn.execute(text("INSERT INTO import_special_events VALUES (7, '2026-09-20',"
                          " 'Three Clay Shoot', 60)"))
        conn.execute(text(f"{EVENT_INSERT}, kind, label, target_total) VALUES ('2026-09-20',"
                          " 'sporting', 'none', 1, 1, true, false, true, 'special',"
                          " 'Three Clay Shoot', 60)"))
        conn.execute(text(f"{EVENT_INSERT}) VALUES ('2026-09-27', 'sporting', 'none', 1, 1,"
                          " true, false, true)"))
        conn.execute(text("INSERT INTO rounds (event_date, shooter_id, name_key, ordinal, score,"
                          " source_row) VALUES ('2026-09-20', 1, 'hadley ike', 1, 55, 5),"
                          " ('2026-09-27', 1, 'hadley ike', 1, 41, 9)"))
    _alembic(scratch_engine, "downgrade", "0007")
    with scratch_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM imports")).scalar_one() == 0
        assert conn.execute(text("SELECT event_date::text FROM events")).scalars().all() == [
            "2026-09-27"
        ]
        assert conn.execute(text("SELECT score FROM rounds")).scalars().all() == [41]
        columns = conn.execute(
            text("SELECT column_name FROM information_schema.columns"
                 " WHERE table_name = 'events' AND column_name IN ('kind', 'label', 'target_total')")
        ).all()
        assert columns == []
    with pytest.raises(IntegrityError, match="ck_imports_kind"), scratch_engine.begin() as conn:
        conn.execute(text("INSERT INTO imports (kind, filename, sha256, file_bytes)"
                          " VALUES ('special', 's.xlsx', 'def', 'x')"))


def test_import_kind_check_accepts_a_special_import(session: Session) -> None:
    session.add(Import(kind="special", filename="s.xlsx", sha256="c" * 64, file_bytes=b"x"))
    session.flush()
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/models/test_schema_0001.py`
Expected: FAIL. `test_upgrade_downgrade_roundtrip` lacks `import_special_events` and cannot downgrade to `0007` from `0007`; the two `0008` tests fail on the missing columns; `test_import_kind_check_accepts_a_special_import` fails with `ck_imports_kind`.

- [ ] **Step 7: Write the migration and the models**

Create `backend/migrations/versions/0008_special_events.py`:

```python
"""special events: an event kind with its own label and target total, and special imports

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-01

Expand-only. `events` gains kind (default 'regular'), label and target_total (default 50); the
previous release never writes them, so its rebuild stores regular Sundays exactly as before.
`imports.kind` also allows 'special', and `import_special_events` holds each special import's
date, label and target total (its rows and stations use the existing staging tables).

Rollback limit: the previous release lists imports through a FileKind without 'special', so its
admin import list fails once a special import exists, and its rebuild drops special Sundays from
the live tables. Roll back to it only before a special shoot is uploaded, or after
`DELETE FROM imports WHERE kind = 'special'` and a rebuild.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SPECIAL_DATES = "SELECT event_date FROM events WHERE kind = 'special'"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_imports_kind"), "imports", type_="check")
    op.create_check_constraint(
        op.f("ck_imports_kind"), "imports", "kind IN ('scores', 'stations', 'special')"
    )
    op.add_column(
        "events",
        sa.Column("kind", sa.Text(), server_default=sa.text("'regular'"), nullable=False),
    )
    op.add_column("events", sa.Column("label", sa.Text(), nullable=True))
    op.add_column(
        "events",
        sa.Column("target_total", sa.SmallInteger(), server_default=sa.text("50"), nullable=False),
    )
    op.create_check_constraint(op.f("ck_events_kind"), "events", "kind IN ('regular', 'special')")
    op.create_table(
        "import_special_events",
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("target_total", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_id"],
            ["imports.id"],
            name=op.f("fk_import_special_events_import_id_imports"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("import_id", name=op.f("pk_import_special_events")),
    )


def downgrade() -> None:
    # Special Sundays cannot exist without the kind: their live rows go now (rebuildable; the
    # analytics tables are rewritten by the next pipeline run), their imports cascade away.
    op.execute(f"DELETE FROM station_hits WHERE event_date IN ({SPECIAL_DATES})")  # noqa: S608
    op.execute(f"DELETE FROM station_layouts WHERE event_date IN ({SPECIAL_DATES})")  # noqa: S608
    op.execute(
        "DELETE FROM round_metrics WHERE round_id IN (SELECT id FROM rounds"  # noqa: S608
        f" WHERE event_date IN ({SPECIAL_DATES}))"
    )
    op.execute(f"DELETE FROM rounds WHERE event_date IN ({SPECIAL_DATES})")  # noqa: S608
    op.execute("DELETE FROM events WHERE kind = 'special'")
    op.execute("DELETE FROM imports WHERE kind = 'special'")
    op.drop_table("import_special_events")
    op.drop_constraint(op.f("ck_events_kind"), "events", type_="check")
    op.drop_column("events", "target_total")
    op.drop_column("events", "label")
    op.drop_column("events", "kind")
    op.drop_constraint(op.f("ck_imports_kind"), "imports", type_="check")
    op.create_check_constraint(op.f("ck_imports_kind"), "imports", "kind IN ('scores', 'stations')")
```

In `backend/src/sunday_clays/models/live.py`, replace

```python
class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "round_type_source IN ('stations', 'override', 'none')",
            name=conv("ck_events_round_type_source"),
        ),
    )
```

with

```python
class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "round_type_source IN ('stations', 'override', 'none')",
            name=conv("ck_events_round_type_source"),
        ),
        CheckConstraint("kind IN ('regular', 'special')", name=conv("ck_events_kind")),
    )
```

and replace

```python
    results_complete: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Round(Base):
```

with

```python
    results_complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Plan 17: a special Sunday counts only as an appearance (frames.load_* filter on it)
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'regular'"))
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_total: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("50")
    )


class Round(Base):
```

In `backend/src/sunday_clays/models/staging.py`, replace

```python
        CheckConstraint("kind IN ('scores', 'stations')", name=conv("ck_imports_kind")),
```

with

```python
        CheckConstraint(
            "kind IN ('scores', 'stations', 'special')", name=conv("ck_imports_kind")
        ),
```

and append:

```python
class ImportSpecialEvent(Base):
    """A special import's Sunday, name and target total (Plan 17); rows and stations are staged
    in import_score_rows and import_station_* under the same import."""

    __tablename__ = "import_special_events"

    import_id: Mapped[int] = mapped_column(
        ForeignKey(
            "imports.id",
            ondelete="CASCADE",
            name=conv("fk_import_special_events_import_id_imports"),
        ),
        primary_key=True,
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    target_total: Mapped[int] = mapped_column(SmallInteger, nullable=False)
```

In `backend/src/sunday_clays/models/__init__.py`, add `ImportSpecialEvent` to the `from sunday_clays.models.staging import (...)` list and to `__all__` (after `"ImportScoreRow"`).

- [ ] **Step 8: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/models/test_schema_0001.py`
Expected: PASS, including `test_migration_matches_models` (`alembic check` finds no drift), `test_check_constraints_match_models` (`ck_events_kind`, widened `ck_imports_kind`) and `test_server_defaults_match_models` (`'regular'`, `50`).

- [ ] **Step 9: Write the failing staging and preview tests**

Append to `backend/tests/conftest.py`:

```python
# --- Plan 17 T1: special-event workbooks ------------------------------------------------------
SPECIAL_SUNDAY = date(2026, 9, 20)  # the fixture has no Sunday on this date
SPECIAL_LABEL = "Three Clay Shoot"
SPECIAL_ENTRIES: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("Hadley, Ike", (6, 5, 6, 4, 6, 5, 6, 6, 5, 6)),  # 55
    ("Kaplan, Noel", (6, 5, 5, 5, 6, 5, 5, 5, 4, 5)),  # 51
    ("Devlin, Sid", (5, 5, 4, 5, 5, 4, 5, 5, 5, 5)),  # 48
    ("Abernathy, Preston", (4, 5, 4, 5, 4, 4, 5, 4, 5, 4)),  # 44
    ("Kim, Pat", (4, 4, 3, 4, 4, 4, 4, 4, 4, 4)),  # 39, not in the fixture: a new shooter
)


def _special_workbook(
    entries: Sequence[tuple[str, Sequence[int]]] = SPECIAL_ENTRIES,
    *,
    event_date: date = SPECIAL_SUNDAY,
    label: str = SPECIAL_LABEL,
    stations: Sequence[object] = tuple(range(1, 11)),
    targets: Sequence[int] = (6,) * 10,
    total: bool = True,
) -> bytes:
    """A special-event workbook (Plan 17 format) with correct totals."""
    import io

    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Special Event"
    sheet.append(["Special event", label])
    sheet.append(["Event date", event_date])
    sheet.append(["Station", *stations, *(["Total"] if total else [])])
    sheet.append(["Targets", *targets])
    for name, hits in entries:
        sheet.append([name, *hits, *([sum(hits)] if total else [])])
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


@pytest.fixture
def special_workbook() -> Callable[..., bytes]:
    return _special_workbook
```

and add to the conftest's imports: `from collections.abc import Callable, Iterator, Sequence` (replacing `from collections.abc import Iterator`) and `from datetime import date`.

Create `backend/tests/integration/domain/test_stage_special.py`:

```python
"""Staging and previewing a special-event import (Plan 17 Task 1)."""

from collections.abc import Callable
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.domain.identity import lookup_shooter
from sunday_clays.domain.imports import (
    active_scores_import,
    active_special_sources,
    active_station_sources,
    commit_import,
    get_import_preview,
    rollback_import,
    stage_import,
)
from sunday_clays.domain.rules import RuleType, create_rule
from sunday_clays.domain.schemas import SpecialDiff
from sunday_clays.ingest.types import FileKind
from sunday_clays.models import (
    ImportScoreRow,
    ImportSpecialEvent,
    ImportStationHit,
    ImportStationLayout,
    ImportStationSheet,
)

SPECIAL = date(2026, 9, 20)
BEFORE = date(2026, 9, 13)
HITS = (5, 5, 5, 5, 5, 5, 5, 5, 5, 5)


def _stage(session: Session, data: bytes, name: str = "special.xlsx") -> tuple[int, SpecialDiff]:
    preview = stage_import(session, data, name)
    assert preview.kind is FileKind.SPECIAL
    assert isinstance(preview.diff, SpecialDiff)
    return preview.import_id, preview.diff


def test_staging_stores_the_sunday_rows_and_stations(
    session: Session, special_workbook: Callable[..., bytes]
) -> None:
    import_id, diff = _stage(session, special_workbook())

    assert (diff.event_date, diff.label, diff.target_total) == (SPECIAL, "Three Clay Shoot", 60)
    assert diff.stations == [str(n) for n in range(1, 11)]
    assert diff.n_shooters == 5
    assert diff.replaces_import is None
    assert diff.regular_rows_on_date == 0
    event = session.get(ImportSpecialEvent, import_id)
    assert event is not None
    assert (event.event_date, event.label, event.target_total) == (SPECIAL, "Three Clay Shoot", 60)
    rows = session.execute(
        select(ImportScoreRow.raw_name, ImportScoreRow.name_key, ImportScoreRow.score,
               ImportScoreRow.event_date, ImportScoreRow.status, ImportScoreRow.gauge_class)
        .where(ImportScoreRow.import_id == import_id)
        .order_by(ImportScoreRow.row_number)
    ).all()
    assert [tuple(r) for r in rows] == [
        ("Hadley, Ike", "hadley ike", 55, SPECIAL, None, None),
        ("Kaplan, Noel", "kaplan noel", 51, SPECIAL, None, None),
        ("Devlin, Sid", "devlin sid", 48, SPECIAL, None, None),
        ("Abernathy, Preston", "abernathy preston", 44, SPECIAL, None, None),
        ("Kim, Pat", "kim pat", 39, SPECIAL, None, None),
    ]
    (sheet,) = session.scalars(
        select(ImportStationSheet).where(ImportStationSheet.import_id == import_id)
    )
    assert (sheet.sheet_name, sheet.event_date) == ("Special Event", SPECIAL)
    layout = session.execute(
        select(ImportStationLayout.station_label, ImportStationLayout.target_count)
        .where(ImportStationLayout.sheet_id == sheet.id)
        .order_by(ImportStationLayout.station_no)
    ).all()
    assert [tuple(r) for r in layout] == [(str(n), 6) for n in range(1, 11)]
    hits = session.scalar(
        select(func.sum(ImportStationHit.hits)).where(ImportStationHit.sheet_id == sheet.id)
    )
    assert hits == 55 + 51 + 48 + 44 + 39


def test_preview_lists_new_names_and_possible_duplicates(
    session: Session,
    special_workbook: Callable[..., bytes],
    seed_live_round: Callable[..., int],
) -> None:
    seed_live_round(session, "Hadley, Ike", BEFORE, 40)
    seed_live_round(session, "Bee, Bob", BEFORE, 38)
    entries = [("Hadley, Ike", HITS), ("Bee, Bobby", HITS), ("Kim, Pat", HITS)]

    _, diff = _stage(session, special_workbook(entries))

    assert diff.new_names == ["Bee, Bobby", "Kim, Pat"]
    assert diff.possible_duplicates == [("Bee, Bob", "Bee, Bobby")]


def test_an_alias_rule_makes_a_name_known_in_the_preview(
    session: Session,
    special_workbook: Callable[..., bytes],
    seed_live_round: Callable[..., int],
) -> None:
    seed_live_round(session, "Ace, Amy", BEFORE, 40)  # creates Amy and her alias
    amy_id = lookup_shooter(session, "ace amy")
    assert amy_id is not None
    create_rule(session, RuleType.ALIAS_NAME, {"name_key": "ace amelia", "shooter_id": amy_id}, None)

    _, diff = _stage(session, special_workbook([("Ace, Amelia", HITS), ("Kim, Pat", HITS)]))

    assert diff.new_names == ["Kim, Pat"]


def test_preview_says_which_live_import_it_replaces(
    session: Session, special_workbook: Callable[..., bytes]
) -> None:
    first, _ = _stage(session, special_workbook())
    commit_import(session, first)
    corrected = special_workbook(label="Three Clay Shoot (corrected)")

    second, diff = _stage(session, corrected, "special-corrected.xlsx")

    assert diff.replaces_import == first
    commit_import(session, second)
    assert active_special_sources(session)[SPECIAL].import_id == second
    rollback_import(session, second)
    assert active_special_sources(session)[SPECIAL].import_id == first
    assert active_special_sources(session)[SPECIAL].label == "Three Clay Shoot"
    rollback_import(session, first)
    assert active_special_sources(session) == {}


def test_regular_rows_on_the_special_date_are_flagged_in_both_previews(
    session: Session,
    special_workbook: Callable[..., bytes],
    scores_workbook: Callable[..., bytes],
) -> None:
    weekly = stage_import(
        session, scores_workbook([("Hadley, Ike", 40, SPECIAL), ("Devlin, Sid", 35, BEFORE)]),
        "scores.xlsx",
    )
    commit_import(session, weekly.import_id)

    special_id, diff = _stage(session, special_workbook())
    assert diff.regular_rows_on_date == 1
    flagged = [f for f in get_import_preview(session, special_id).findings
               if f.code == "regular_scores_on_special_date"]
    assert [(f.severity.value, f.event_date, f.message) for f in flagged] == [
        ("warning", SPECIAL,
         "The live scores workbook has 1 rows on this date; they are left out while this "
         "special shoot is live"),
    ]
    commit_import(session, special_id)

    again = stage_import(
        session, scores_workbook([("Hadley, Ike", 41, SPECIAL), ("Devlin, Sid", 35, BEFORE)]),
        "scores-again.xlsx",
    )
    flagged = [f for f in again.findings if f.code == "special_event_date"]
    assert [(f.severity.value, f.event_date, f.sheet, f.message) for f in flagged] == [
        ("warning", SPECIAL, "ALL SCORE DETAIL",
         "2026-09-20 is the special shoot 'Three Clay Shoot': its 1 rows here are left out "
         "while that import is live"),
    ]
    assert all(f.event_date != BEFORE for f in flagged)


def test_a_duplicate_upload_returns_the_stored_special_preview(
    session: Session, special_workbook: Callable[..., bytes]
) -> None:
    data = special_workbook()
    first, diff = _stage(session, data)

    again = stage_import(session, data, "same.xlsx")

    assert again.duplicate_of == first
    assert again.diff == diff
    assert get_import_preview(session, first).diff == diff


def test_a_special_import_is_never_a_scores_or_stations_source(
    session: Session, special_workbook: Callable[..., bytes]
) -> None:
    import_id, _ = _stage(session, special_workbook())
    commit_import(session, import_id)

    assert active_scores_import(session) is None
    assert active_station_sources(session) == {}
    source = active_special_sources(session)[SPECIAL]
    assert (source.import_id, source.label, source.target_total) == (import_id, "Three Clay Shoot", 60)
```

In `backend/tests/integration/api/test_admin_imports_api.py`, append:

```python
def test_a_special_workbook_uploads_as_its_own_kind(
    admin_client: TestClient, special_workbook: Callable[..., bytes], session: Session
) -> None:
    preview = _upload(admin_client, special_workbook(), "three-clay.xlsx")

    assert preview["kind"] == "special"
    assert preview["diff"]["label"] == "Three Clay Shoot"
    assert preview["diff"]["target_total"] == 60
    assert preview["diff"]["n_shooters"] == 5
    assert preview["requires_removal_confirmation"] is False
    listed = admin_client.get("/api/admin/imports").json()
    assert listed[0]["kind"] == "special"
    commit = admin_client.post(f"/api/admin/imports/{preview['import_id']}/commit")
    assert commit.status_code == 200, commit.text
    assert _status(session, preview["import_id"]) == "committed"
```

and add `from collections.abc import Callable` to its imports.

- [ ] **Step 10: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/domain/test_stage_special.py tests/integration/api/test_admin_imports_api.py -k "special or Special"`
Expected: FAIL at import: `ImportError: cannot import name 'active_special_sources'` / `'SpecialDiff'`; the API test fails with 400 `unreadable_file` ("Special shoot imports are not ready yet").

- [ ] **Step 11: Write the schema, staging and preview**

In `backend/src/sunday_clays/domain/schemas.py`, add after `StationsDiff`:

```python
class SpecialDiff(BaseModel):
    """A special-event import (Plan 17): the one Sunday it adds or replaces."""

    event_date: date
    label: str
    target_total: int
    stations: list[str]
    n_shooters: int
    replaces_import: int | None  # the live special import of this date a commit replaces
    regular_rows_on_date: int  # weekly-workbook rows on this date, left out while it is live
    new_names: list[str]
    possible_duplicates: list[tuple[str, str]]
```

and in `ImportPreview` replace `    diff: ScoresDiff | StationsDiff` with `    diff: ScoresDiff | StationsDiff | SpecialDiff`.

In `backend/src/sunday_clays/domain/imports.py`:

1. Imports. Replace

```python
import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
```

with

```python
import hashlib
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
```

replace

```python
from sunday_clays.domain.schemas import (
    FindingOut,
    ImportPreview,
    ImportSummary,
    ScoresDiff,
    StationsDiff,
    finding_out,
)
```

with

```python
from sunday_clays.domain.schemas import (
    FindingOut,
    ImportPreview,
    ImportSummary,
    ScoresDiff,
    SpecialDiff,
    StationsDiff,
    finding_out,
)
```

and replace the `ingest.types` and `models` imports (including the two names Step 3 added) with

```python
from sunday_clays.ingest.types import (
    STATION_SHEET_EXCLUSION_CODES,
    FileKind,
    Finding,
    ScoresParse,
    Severity,
    SpecialParse,
    StationHitsRow,
    StationSheet,
    StationsParse,
)
from sunday_clays.ingest.workbook import SCORES_SHEET, SPECIAL_SHEET
from sunday_clays.models import (
    Import,
    ImportAttendanceRow,
    ImportScoreRow,
    ImportSpecialEvent,
    ImportStationHit,
    ImportStationLayout,
    ImportStationSheet,
    Round,
    Shooter,
    ShooterAlias,
    StationHit,
)
```

2. After `active_station_sources`, add:

```python
@dataclass(frozen=True)
class SpecialSource:
    """The live special import of one Sunday (Plan 17)."""

    import_id: int
    sheet_id: int  # its one import_station_sheets row
    label: str
    target_total: int


def active_special_sources(session: Session) -> dict[date, SpecialSource]:
    """event_date -> the newest committed special import with that date (Decision 14)."""
    rows = session.execute(
        select(
            ImportSpecialEvent.event_date,
            ImportSpecialEvent.import_id,
            ImportStationSheet.id,
            ImportSpecialEvent.label,
            ImportSpecialEvent.target_total,
        )
        .join(Import, Import.id == ImportSpecialEvent.import_id)
        .join(ImportStationSheet, ImportStationSheet.import_id == ImportSpecialEvent.import_id)
        .where(Import.kind == FileKind.SPECIAL.value, Import.status == "committed")
        .order_by(Import.committed_at.desc(), Import.id.desc())
    ).all()
    sources: dict[date, SpecialSource] = {}
    for event_date, import_id, sheet_id, label, target_total in rows:
        sources.setdefault(event_date, SpecialSource(import_id, sheet_id, label, target_total))
    return dict(sorted(sources.items()))
```

3. After `_stage_stations`, add:

```python
def _stage_special(session: Session, import_id: int, parsed: SpecialParse) -> None:
    """The Sunday in import_special_events, one score row per shooter (the recomputed total),
    and the stations as one station sheet named after the special sheet."""
    session.add(
        ImportSpecialEvent(
            import_id=import_id,
            event_date=parsed.event_date,
            label=parsed.label,
            target_total=parsed.target_total,
        )
    )
    session.execute(
        insert(ImportScoreRow).execution_options(render_nulls=True),
        [
            {
                "import_id": import_id,
                "row_number": r.row_number,
                "raw_name": r.raw_name,
                "name_key": identity_key(name_key(r.raw_name), parsed.event_date),
                "score": r.total,
                "event_date": parsed.event_date,
                "status": None,
                "gauge_class": None,
            }
            for r in parsed.rows
        ],
    )
    sheet = StationSheet(
        SPECIAL_SHEET,
        parsed.event_date,
        parsed.layout,
        tuple(StationHitsRow(r.row_number, r.raw_name, r.hits) for r in parsed.rows),
    )
    _stage_stations(session, import_id, StationsParse((sheet,), ()))
```

4. Replace the body of `_preview_scores` from `    aliases: dict[str, int] = dict(` down to its `return` with

```python
    aliases: dict[str, int] = dict(
        session.execute(select(ShooterAlias.name_key, ShooterAlias.shooter_id)).all()
    )
    new_keys = sorted({r.name_key for r in new_rows} - aliases.keys())
    new_names, duplicates = _name_hints(session, new_rows, new_keys, aliases)
    diff = ScoresDiff(
        events_added=changes.events_added,
        events_removed=changes.events_removed,
        rows_added=changes.rows_added,
        rows_removed=changes.rows_removed,
        rows_changed=changes.rows_changed,
        new_names=new_names,
        possible_duplicates=duplicates,
        attendance_changed=attendance,
    )
    return diff, [
        *_scores_station_findings(session, new_rows, aliases),
        *_special_date_findings(session, new_rows),
    ]


def _name_hints(
    session: Session,
    rows: Sequence[StagedScore],
    new_keys: Sequence[str],
    aliases: Mapping[str, int],
) -> tuple[list[str], list[tuple[str, str]]]:
    """Display names of `new_keys` and their possible duplicates among every known name.

    Known names' dates are their live rounds' dates; a staged key's dates are its staged dates.
    """
    staged_names = representative_names(rows)
    key_dates: dict[str, set[date]] = defaultdict(set)
    for key, event_date in session.execute(select(Round.name_key, Round.event_date).distinct()):
        key_dates[key].add(event_date)
    for key in aliases:
        key_dates.setdefault(key, set())
    staged_dates: dict[str, set[date]] = defaultdict(set)
    for row in rows:
        staged_dates[row.name_key].add(row.event_date)
    key_dates.update(staged_dates)
    display: dict[str, str] = dict(
        session.execute(
            select(ShooterAlias.name_key, Shooter.display_name).join(
                Shooter, Shooter.id == ShooterAlias.shooter_id
            )
        ).all()
    )
    display.update({k: clean_display_name(raw) for k, raw in staged_names.items()})
    return (
        sorted(display[k] for k in new_keys),
        possible_duplicate_pairs(new_keys, key_dates, display),
    )


def _special_date_findings(session: Session, rows: Sequence[StagedScore]) -> list[Finding]:
    """Scores-workbook rows on a live special Sunday: flagged, never merged (Decision 13)."""
    specials = active_special_sources(session)
    counts = Counter(r.event_date for r in rows if r.event_date in specials)
    return [
        Finding(
            "special_event_date",
            Severity.WARNING,
            f"{day.isoformat()} is the special shoot {specials[day].label!r}: its {n} rows here"
            " are left out while that import is live",
            sheet=SCORES_SHEET,
            event_date=day,
        )
        for day, n in sorted(counts.items())
    ]


def _regular_rows_on(session: Session, event_date: date) -> int:
    """Rows the live scores import has on `event_date` (0 with no live scores import)."""
    active = active_scores_import(session)
    if active is None:
        return 0
    return int(
        session.scalar(
            select(func.count())
            .select_from(ImportScoreRow)
            .where(ImportScoreRow.import_id == active, ImportScoreRow.event_date == event_date)
        )
        or 0
    )


def _preview_special(
    session: Session, import_id: int, parsed: SpecialParse
) -> tuple[SpecialDiff, list[Finding]]:
    rows = load_staged_scores(session, import_id)
    resolve = identity_resolver(session)  # alias_name rules first, then aliases, then merges
    aliases: dict[str, int] = dict(
        session.execute(select(ShooterAlias.name_key, ShooterAlias.shooter_id)).all()
    )
    new_keys = sorted({r.name_key for r in rows if resolve(r.name_key) is None})
    new_names, duplicates = _name_hints(session, rows, new_keys, aliases)
    live = active_special_sources(session).get(parsed.event_date)
    regular = _regular_rows_on(session, parsed.event_date)
    diff = SpecialDiff(
        event_date=parsed.event_date,
        label=parsed.label,
        target_total=parsed.target_total,
        stations=[entry.label for entry in parsed.layout],
        n_shooters=len({r.name_key for r in rows}),
        replaces_import=None if live is None else live.import_id,
        regular_rows_on_date=regular,
        new_names=new_names,
        possible_duplicates=duplicates,
    )
    if regular == 0:
        return diff, []
    return diff, [
        Finding(
            "regular_scores_on_special_date",
            Severity.WARNING,
            f"The live scores workbook has {regular} rows on this date; they are left out while"
            " this special shoot is live",
            event_date=parsed.event_date,
        )
    ]
```

5. In `stage_import`, replace

```python
    diff: ScoresDiff | StationsDiff
```

with

```python
    diff: ScoresDiff | StationsDiff | SpecialDiff
```

and replace the placeholder branch from Step 3

```python
    elif isinstance(parsed, SpecialParse):
        raise ParseError("Special shoot imports are not ready yet")  # replaced in Step 11
```

with

```python
    elif isinstance(parsed, SpecialParse):
        _stage_special(session, imp.id, parsed)
        diff, station_findings = _preview_special(session, imp.id, parsed)
        requires_confirmation = False
```

and remove `ParseError` from the `ingest.types` import if nothing else uses it. Then widen `_placed_findings`, which now also receives a special parse: replace

```python
def _placed_findings(parsed: ScoresParse | StationsParse) -> list[Finding]:
```

with

```python
def _placed_findings(parsed: ScoresParse | StationsParse | SpecialParse) -> list[Finding]:
```

6. In `get_import_preview`, replace

```python
    diff = (
        ScoresDiff.model_validate(stored)
        if kind is FileKind.SCORES
        else StationsDiff.model_validate(stored)
    )
```

with

```python
    diff: ScoresDiff | StationsDiff | SpecialDiff
    if kind is FileKind.SCORES:
        diff = ScoresDiff.model_validate(stored)
    elif kind is FileKind.SPECIAL:
        diff = SpecialDiff.model_validate(stored)
    else:
        diff = StationsDiff.model_validate(stored)
```

- [ ] **Step 12: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/domain/test_stage_special.py tests/integration/domain/test_stage_import.py tests/integration/domain/test_import_lifecycle.py tests/integration/api/test_admin_imports_api.py`
Expected: all pass. The existing scores-preview tests (`test_new_names_and_possible_duplicates_against_known_shooters`, the 25 possible duplicates of the fixture) pass unchanged through `_name_hints`.

- [ ] **Step 12a: Write the failing frontend check (the widened preview union)**

`ImportPreview.diff` now has a third member, and CI's `pnpm typecheck` regenerates the TS schema from this backend. `StationsDiff` is `Exclude<diff, ScoresDiff>`, so it silently becomes `StationsDiff | SpecialDiff`, and `StationsDiffView` stops compiling. Pin the types now; Task 7 draws the special preview.

Add to `frontend/src/features/admin/components/DiffSummary.test.tsx`, inside `describe('DiffSummary', …)`:

```tsx
  it('shows an empty Changes card for a special-shoot preview until its view lands (Plan 17 T7)', () => {
    const special = {
      event_date: '2026-09-20',
      label: 'Three Clay Shoot',
      target_total: 60,
      stations: ['1', '2'],
      n_shooters: 5,
      replaces_import: null,
      regular_rows_on_date: 0,
      new_names: [],
      possible_duplicates: [],
    };
    renderWithProviders(<DiffSummary diff={special} />);
    const card = screen.getByRole('region', { name: 'Changes' });
    expect(within(card).queryByText('Weeks replaced')).not.toBeInTheDocument();
    expect(within(card).queryByText('Rows added')).not.toBeInTheDocument();
  });
```

Run: `cd frontend && pnpm typecheck; pnpm exec vitest run src/features/admin/components/DiffSummary.test.tsx`
Expected: FAIL. `tsc` reports `Property 'events_replaced' does not exist on type … SpecialDiff …` in `DiffSummary.tsx`, and the new test throws on `diff.events_replaced` being undefined (`Cannot read properties of undefined (reading 'length')` from `dateList`).

- [ ] **Step 12b: Pin the diff types and narrow the view**

In `frontend/src/features/admin/api.ts`, replace

```ts
export type StationsDiff = Exclude<ImportPreview['diff'], ScoresDiff>;
```

with

```ts
export type StationsDiff = Extract<ImportPreview['diff'], { events_replaced: string[] }>;
export type SpecialDiff = Extract<ImportPreview['diff'], { target_total: number }>;
```

In `frontend/src/features/admin/components/DiffSummary.tsx`, replace

```tsx
      {'rows_added' in diff ? <ScoresDiffView diff={diff} /> : <StationsDiffView diff={diff} />}
```

with

```tsx
      {'rows_added' in diff ? (
        <ScoresDiffView diff={diff} />
      ) : 'events_replaced' in diff ? (
        <StationsDiffView diff={diff} />
      ) : null}
```

Run: `cd frontend && pnpm typecheck && pnpm exec vitest run src/features/admin && pnpm lint && pnpm exec prettier --check .`
Expected: PASS, every admin test green.

- [ ] **Step 13: Gates and the full backend suite with coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest -q --cov --cov-branch`
Expected: "All checks passed!", "N files already formatted", "Success: no issues found", the whole suite green (golden counts untouched), coverage at or above 90% lines and 90% branches.

- [ ] **Step 14: Commit**

```bash
git add backend/src/sunday_clays/ingest/types.py backend/src/sunday_clays/ingest/workbook.py backend/src/sunday_clays/ingest/special.py backend/src/sunday_clays/ingest/validate.py backend/src/sunday_clays/ingest/__init__.py backend/migrations/versions/0008_special_events.py backend/src/sunday_clays/models/live.py backend/src/sunday_clays/models/staging.py backend/src/sunday_clays/models/__init__.py backend/src/sunday_clays/domain/schemas.py backend/src/sunday_clays/domain/imports.py backend/tests/unit/ingest/builders_special.py backend/tests/unit/ingest/test_special.py backend/tests/unit/ingest/test_workbook.py backend/tests/unit/ingest/test_parse_upload.py backend/tests/integration/models/test_schema_0001.py backend/tests/conftest.py backend/tests/integration/domain/test_stage_special.py backend/tests/integration/api/test_admin_imports_api.py frontend/src/features/admin/api.ts frontend/src/features/admin/components/DiffSummary.tsx frontend/src/features/admin/components/DiffSummary.test.tsx
git commit -m "feat(special): special-event workbook, migration 0008, staging and preview (Plan 17 T1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Special Sundays in the live tables, and the `fx_special` world

The rebuild puts each date's live special import into `events`/`rounds`/`station_*`, books names through alias rules, keeps profiles' round counts to regular rounds, and leaves weekly rows on a special date out. The task also adds the session-scoped special world that every later no-leak test compares against `fx_*`.

**Files:**
- Modify: `backend/src/sunday_clays/domain/identity.py` (add `alias_rule_targets`)
- Modify: `backend/src/sunday_clays/domain/rebuild.py`
- Modify: `backend/src/sunday_clays/domain/imports.py` (`_scores_station_findings` skips special sheets)
- Modify: `backend/tests/conftest.py` (append the `fx_special_*` fixtures)
- Create: `backend/tests/integration/domain/test_rebuild_special.py`
- Create: `backend/tests/integration/special/test_special_world.py`

**Interfaces:**
- Consumes: Task 1's `active_special_sources`, `SpecialSource`, `special_workbook`/`_special_workbook`, `SPECIAL_ENTRIES`; `domain.identity.{resolve_shooter, lookup_shooter, merge_map}`; the fixtures `session`, `scores_workbook`, `live_rows`, `engine`, `test_settings`, `auth_env`.
- Produces:
  - `domain.identity.alias_rule_targets(session) -> dict[str, int]` (newest active `alias_name` rule per name key).
  - Live special Sundays: `events.kind = 'special'`, `label`, `target_total`, `round_type = 'sporting'`/`'none'` unless overridden; rounds and linked station hits; `shooter_profiles.n_rounds` counts regular rounds only; data issue `special_event_date_conflict` with `details = {"rows": n, "special_import_id": id}`.
  - Fixtures `fx_special_engine` (session), `fx_special_session`, `fx_special_client`, `fx_special_viewer_client`: the `fx` world plus 2026-09-20 "Three Clay Shoot" (Decision 23).

- [ ] **Step 1: Write the failing rebuild tests**

Create `backend/tests/integration/domain/test_rebuild_special.py`:

```python
"""Special Sundays in the live tables (Plan 17 Task 2)."""

from collections.abc import Callable
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.domain.identity import lookup_shooter
from sunday_clays.domain.imports import commit_import, rollback_import, stage_import
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.domain.rules import RuleType, create_rule
from sunday_clays.models import (
    DataIssue,
    Event,
    Round,
    Shooter,
    ShooterProfile,
    StationHit,
    StationLayout,
)

BEFORE, SPECIAL, AFTER = date(2026, 9, 13), date(2026, 9, 20), date(2026, 9, 27)
WEEKLY: list[tuple[object, ...]] = [
    ("Hadley, Ike", 41, BEFORE),
    ("Devlin, Sid", 35, BEFORE),
    ("Hadley, Ike", 43, AFTER),
    ("Devlin, Sid", 37, AFTER),
]
FIVES = (5,) * 10
STATION_CODES = {"station_score_mismatch", "station_name_unmatched", "station_round_ambiguous"}


def _commit(session: Session, data: bytes, name: str) -> int:
    preview = stage_import(session, data, name)
    commit_import(session, preview.import_id)
    return preview.import_id


def _scores_on(session: Session, day: date) -> dict[str, int]:
    rows = session.execute(
        select(Shooter.display_name, Round.score)
        .join(Shooter, Shooter.id == Round.shooter_id)
        .where(Round.event_date == day)
    ).all()
    return {str(name): int(score) for name, score in rows}


def _live_special(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
    weekly: list[tuple[object, ...]] = WEEKLY,
) -> int:
    _commit(session, scores_workbook(weekly), "scores.xlsx")
    special_id = _commit(session, special_workbook(), "special.xlsx")
    rebuild_live(session)
    return special_id


def test_a_special_sunday_goes_live_with_its_label_rounds_and_stations(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    _live_special(session, scores_workbook, special_workbook)

    event = session.get(Event, SPECIAL)
    assert event is not None
    assert (event.kind, event.label, event.target_total) == ("special", "Three Clay Shoot", 60)
    assert (event.round_type, event.round_type_source) == ("sporting", "none")
    assert (
        event.n_rounds,
        event.n_shooters,
        event.has_scores,
        event.has_stations,
        event.results_complete,
    ) == (5, 5, True, True, True)
    for day in (BEFORE, AFTER):
        regular = session.get(Event, day)
        assert regular is not None
        assert (regular.kind, regular.label, regular.target_total) == ("regular", None, 50)
    assert _scores_on(session, SPECIAL) == {
        "Hadley, Ike": 55,
        "Kaplan, Noel": 51,
        "Devlin, Sid": 48,
        "Abernathy, Preston": 44,
        "Kim, Pat": 39,
    }
    layout = session.execute(
        select(StationLayout.station_label, StationLayout.target_count)
        .where(StationLayout.event_date == SPECIAL)
        .order_by(StationLayout.station_no)
    ).all()
    assert [tuple(r) for r in layout] == [(str(n), 6) for n in range(1, 11)]
    hits = session.scalars(select(StationHit).where(StationHit.event_date == SPECIAL)).all()
    assert len(hits) == 50
    assert all(h.round_id is not None and h.shooter_id is not None for h in hits)
    assert session.scalars(select(DataIssue.code).where(DataIssue.event_date == SPECIAL)).all() == []


def test_profiles_count_the_special_sunday_as_an_event_but_not_a_round(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    _live_special(session, scores_workbook, special_workbook)

    hadley = session.get(ShooterProfile, lookup_shooter(session, "hadley ike"))
    assert hadley is not None
    assert (hadley.n_events, hadley.n_rounds, hadley.first_event, hadley.last_event) == (
        3,
        2,
        BEFORE,
        AFTER,
    )
    kim = session.get(ShooterProfile, lookup_shooter(session, "kim pat"))
    assert kim is not None
    assert (kim.display_name, kim.status, kim.n_events, kim.n_rounds) == ("Kim, Pat", "guest", 1, 0)
    assert (kim.first_event, kim.last_event) == (SPECIAL, SPECIAL)


def test_weekly_rows_on_a_special_date_are_left_out_and_come_back_on_rollback(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    special_id = _live_special(
        session, scores_workbook, special_workbook, [*WEEKLY, ("Hadley, Ike", 40, SPECIAL)]
    )

    assert _scores_on(session, SPECIAL)["Hadley, Ike"] == 55
    assert len(_scores_on(session, SPECIAL)) == 5
    issue = session.execute(
        select(DataIssue.code, DataIssue.severity, DataIssue.details).where(
            DataIssue.event_date == SPECIAL
        )
    ).one()
    assert (issue.code, issue.severity) == ("special_event_date_conflict", "warning")
    assert issue.details == {"rows": 1, "special_import_id": special_id}

    rollback_import(session, special_id)
    rebuild_live(session)

    event = session.get(Event, SPECIAL)
    assert event is not None
    assert (event.kind, event.label, event.target_total, event.n_rounds) == ("regular", None, 50, 1)
    assert _scores_on(session, SPECIAL) == {"Hadley, Ike": 40}


def test_a_newer_special_import_replaces_the_older_one_and_rollback_restores_it(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    first = _live_special(session, scores_workbook, special_workbook)
    corrected = special_workbook(
        [("Hadley, Ike", (6, 5, 6, 4, 6, 5, 6, 6, 5, 3))], label="Three Clay Shoot (corrected)"
    )
    second = _commit(session, corrected, "special-corrected.xlsx")
    rebuild_live(session)

    event = session.get(Event, SPECIAL)
    assert event is not None
    assert (event.label, event.n_shooters) == ("Three Clay Shoot (corrected)", 1)
    assert _scores_on(session, SPECIAL) == {"Hadley, Ike": 52}

    rollback_import(session, second)
    rebuild_live(session)
    event = session.get(Event, SPECIAL)
    assert event is not None
    assert (event.label, event.n_shooters) == ("Three Clay Shoot", 5)

    rollback_import(session, first)
    rebuild_live(session)
    assert session.get(Event, SPECIAL) is None
    assert _scores_on(session, SPECIAL) == {}
    assert session.scalar(
        select(func.count()).select_from(StationHit).where(StationHit.event_date == SPECIAL)
    ) == 0


def test_alias_rules_book_special_rows_to_the_existing_shooter(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    _commit(session, scores_workbook([*WEEKLY, ("Ace, Amy", 40, BEFORE)]), "scores.xlsx")
    rebuild_live(session)
    amy = lookup_shooter(session, "ace amy")
    assert amy is not None
    create_rule(session, RuleType.ALIAS_NAME, {"name_key": "ace amelia", "shooter_id": amy}, None)
    _commit(session, special_workbook([("Ace, Amelia", FIVES), ("Kim, Pat", FIVES)]), "s.xlsx")
    shooters_before = session.scalar(select(func.count()).select_from(Shooter))

    rebuild_live(session)

    booked = session.scalar(
        select(Round.shooter_id).where(Round.event_date == SPECIAL, Round.name_key == "ace amelia")
    )
    assert booked == amy
    assert session.scalar(select(func.count()).select_from(Shooter)) == shooters_before + 1  # Kim
    assert session.scalar(select(Shooter.id).where(Shooter.display_name == "Ace, Amelia")) is None
    profile = session.get(ShooterProfile, amy)
    assert profile is not None
    assert (profile.n_events, profile.n_rounds) == (2, 1)
    hit = session.scalar(
        select(StationHit.round_id).where(
            StationHit.event_date == SPECIAL, StationHit.name_key == "ace amelia"
        ).limit(1)
    )
    assert hit is not None  # the station row links to the booked round


def test_alias_rules_still_leave_weekly_rows_alone(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    _commit(session, scores_workbook([*WEEKLY, ("Ace, Amy", 40, BEFORE)]), "scores.xlsx")
    rebuild_live(session)
    amy = lookup_shooter(session, "ace amy")
    assert amy is not None
    create_rule(session, RuleType.ALIAS_NAME, {"name_key": "ace amelia", "shooter_id": amy}, None)
    _commit(session, scores_workbook([*WEEKLY, ("Ace, Amy", 40, BEFORE), ("Ace, Amelia", 30, AFTER)]),
            "scores-2.xlsx")
    _commit(session, special_workbook([("Kim, Pat", FIVES)]), "s.xlsx")

    rebuild_live(session)

    weekly = session.scalar(
        select(Round.shooter_id).where(Round.event_date == AFTER, Round.name_key == "ace amelia")
    )
    assert weekly is not None and weekly != amy  # Decision 15: today's behaviour for weekly rows


def test_a_round_type_override_still_applies_to_a_special_sunday(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    create_rule(
        session,
        RuleType.ROUND_TYPE_OVERRIDE,
        {"event_date": SPECIAL.isoformat(), "round_type": "super_sporting"},
        None,
    )
    _live_special(session, scores_workbook, special_workbook)

    event = session.get(Event, SPECIAL)
    assert event is not None
    assert (event.kind, event.round_type, event.round_type_source) == (
        "special",
        "super_sporting",
        "override",
    )


def test_a_rebuild_with_a_special_sunday_is_idempotent(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
    live_rows: Callable[[Session], dict[str, list[dict[str, Any]]]],
) -> None:
    _live_special(session, scores_workbook, special_workbook)
    first = live_rows(session)
    rebuild_live(session)
    assert live_rows(session) == first


def test_the_scores_preview_never_checks_a_special_sheet_against_weekly_rows(
    session: Session,
    scores_workbook: Callable[..., bytes],
    special_workbook: Callable[..., bytes],
) -> None:
    _live_special(session, scores_workbook, special_workbook)

    preview = stage_import(
        session, scores_workbook([*WEEKLY, ("Hadley, Ike", 40, SPECIAL)]), "scores-2.xlsx"
    )

    assert [f.code for f in preview.findings if f.event_date == SPECIAL] == ["special_event_date"]
    assert not [f for f in preview.findings if f.code in STATION_CODES]
```

Create `backend/tests/integration/special/test_special_world.py`:

```python
"""The fx_special world is the fx world plus one special Sunday (Plan 17 Task 2)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.models import Event, Round, Shooter

SPECIAL = date(2026, 9, 20)


def test_the_special_world_is_the_fixture_world_plus_one_special_sunday(
    fx_session: Session, fx_special_session: Session
) -> None:
    base = {tuple(r) for r in fx_session.execute(select(Event.event_date, Event.n_rounds))}
    special = fx_special_session.execute(
        select(Event.event_date, Event.n_rounds, Event.kind, Event.label, Event.target_total)
    ).all()

    assert {(d, n) for d, n, kind, _, _ in special if kind == "regular"} == base
    assert [tuple(r) for r in special if r[2] == "special"] == [
        (SPECIAL, 5, "special", "Three Clay Shoot", 60)
    ]
    scores = fx_special_session.execute(
        select(Shooter.display_name, Round.score)
        .join(Shooter, Shooter.id == Round.shooter_id)
        .where(Round.event_date == SPECIAL)
        .order_by(Round.score.desc())
    ).all()
    assert [tuple(r) for r in scores] == [
        ("Hadley, Ike", 55),
        ("Kaplan, Noel", 51),
        ("Devlin, Sid", 48),
        ("Abernathy, Preston", 44),
        ("Kim, Pat", 39),
    ]
```

Append to `backend/tests/conftest.py`:

```python
# --- Plan 17 T2: the committed-fixtures world plus one special Sunday --------------------------
@pytest.fixture(scope="session")
def fx_special_engine(engine: Engine) -> Iterator[Engine]:
    """`fx_engine`'s world built the same way, plus the special Sunday 2026-09-20 (Plan 17).

    SPECIAL_ENTRIES: four fixture shooters who shot 2026-09-13 and 2026-09-27, and Kim, Pat, who
    is new. Its own database, so the analytics memo (keyed by database name) never mixes it with
    fx_engine; tests that read both worlds still call clear_cache() between them.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    from sunday_clays.analytics.pipeline import run_pipeline
    from sunday_clays.domain.imports import commit_import, stage_import
    from sunday_clays.domain.rebuild import rebuild_live

    url = engine.url.set(database=f"{engine.url.database}_fx_special")
    drop = f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'
    admin = create_engine(
        engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    with admin.connect() as conn:
        conn.exec_driver_sql(drop)
        conn.exec_driver_sql(f'CREATE DATABASE "{url.database}"')
    world = make_engine(url.render_as_string(hide_password=False))
    try:
        config = alembic_config()
        with world.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        uploads = [
            (name, (FIXTURES_DIR / name).read_bytes())
            for name in ("scores_2026-09-27.xlsx", "stations_2026-09-27.xlsx")
        ]
        uploads.append(("special_2026-09-20.xlsx", _special_workbook()))
        with Session(world) as setup:
            for filename, data in uploads:
                preview = stage_import(setup, data, filename)
                commit_import(setup, preview.import_id)
                rebuild_live(setup)
            load_weather_fixture(setup)
            run_pipeline(setup)
            setup.commit()
        yield world
    finally:
        world.dispose()
        with admin.connect() as conn:
            conn.exec_driver_sql(drop)
        admin.dispose()


@pytest.fixture
def fx_special_session(fx_special_engine: Engine) -> Iterator[Session]:
    """Like ``fx_session``, on the special-Sunday world."""
    connection = fx_special_engine.connect()
    outer = connection.begin()
    db_session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield db_session
    finally:
        db_session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def fx_special_client(fx_special_session: Session, test_settings: Settings) -> Iterator[TestClient]:
    """Like ``fx_client``, bound to ``fx_special_session``."""
    app = create_app()

    def session_override() -> Iterator[Session]:
        nested = fx_special_session.begin_nested()
        try:
            yield fx_special_session
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


@pytest.fixture
def fx_special_viewer_client(
    fx_special_client: TestClient, auth_env: Settings
) -> Iterator[TestClient]:
    logged_in = _logged_in(_use_env_settings(fx_special_client), "viewer")
    yield logged_in
    logged_in.close()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/domain/test_rebuild_special.py tests/integration/special/test_special_world.py`
Expected: FAIL. No `events` row on 2026-09-20 (the rebuild ignores special imports), so `event` is `None`; the conflict test finds the weekly 40 as the only 2026-09-20 round; the preview test sees a `station_score_mismatch`; the world test finds no special row.

- [ ] **Step 3: Write `alias_rule_targets`**

Append to `backend/src/sunday_clays/domain/identity.py`:

```python
def alias_rule_targets(session: Session) -> dict[str, int]:
    """name_key -> shooter id of its newest active alias_name rule (Plan 17, special rows).

    Ascending ids, so the newest rule per key is the one left in the dict; merges are applied by
    the caller, as for every other shooter id.
    """
    payloads: list[dict[str, Any]] = list(
        session.scalars(
            select(Rule.payload)
            .where(Rule.rule_type == "alias_name", Rule.active.is_(True))
            .order_by(Rule.id)
        )
    )
    return {str(p["name_key"]): int(p["shooter_id"]) for p in payloads}
```

- [ ] **Step 4: Write the rebuild changes**

In `backend/src/sunday_clays/domain/rebuild.py`:

1. Replace

```python
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
```

with

```python
from collections import Counter, defaultdict
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
```

replace

```python
from sunday_clays.domain.identity import identity_resolver, merge_map, resolve_shooter
from sunday_clays.domain.imports import (
    active_scores_import,
    active_station_sources,
    load_staged_attendance,
    load_staged_scores,
)
```

with

```python
from sunday_clays.domain.identity import (
    alias_rule_targets,
    identity_resolver,
    merge_map,
    resolve_shooter,
)
from sunday_clays.domain.imports import (
    SpecialSource,
    active_scores_import,
    active_special_sources,
    active_station_sources,
    load_staged_attendance,
    load_staged_scores,
)
```

and add below `LEFT_CENSOR_DAYS = 56`:

```python
REGULAR_TARGETS = 50  # a regular Sunday's round; a special Sunday carries its own total
```

2. In `rebuild_live`, replace

```python
    active_id = active_scores_import(session)
    rounds = _live_rounds(session, load_staged_scores(session, active_id), rules, merges, issues)
    sources = active_station_sources(session)
    layouts = _station_layouts(session, sources)
    attendance = load_staged_attendance(session, active_id)
    n_events = _write_events(session, rounds, attendance, layouts, rules, issues)
    _write_rounds(session, rounds)
    _write_station_data(session, sources, layouts, issues)
    n_profiles = _write_profiles(session, rounds, rules, merges)
```

with

```python
    active_id = active_scores_import(session)
    specials = active_special_sources(session)
    staged, special_keys = _with_special_rows(
        session, load_staged_scores(session, active_id), specials, issues
    )
    rounds = _live_rounds(session, staged, rules, merges, issues, special_keys)
    # a special Sunday's own sheet wins over a station workbook tab of the same date
    sources = dict(
        sorted(
            {
                **active_station_sources(session),
                **{day: source.sheet_id for day, source in specials.items()},
            }.items()
        )
    )
    layouts = _station_layouts(session, sources)
    attendance = load_staged_attendance(session, active_id)
    n_events = _write_events(session, rounds, attendance, layouts, rules, issues, specials)
    _write_rounds(session, rounds)
    _write_station_data(session, sources, layouts, issues)
    n_profiles = _write_profiles(session, rounds, rules, merges, specials.keys())
```

3. Add before `_live_rounds`:

```python
def _with_special_rows(
    session: Session,
    weekly: list[StagedScore],
    specials: Mapping[date, SpecialSource],
    issues: list[DataIssue],
) -> tuple[list[StagedScore], set[str]]:
    """The scores import's rows minus any on a live special Sunday, plus every special row.

    A special import owns its date (Decision 13): weekly rows on it are left out and reported.
    Returns the rows and the name keys found on special sheets.
    """
    left_out = Counter(row.event_date for row in weekly if row.event_date in specials)
    for day, n in sorted(left_out.items()):
        issues.append(
            DataIssue(
                code="special_event_date_conflict",
                severity="warning",
                event_date=day,
                message=(
                    f"{n} scores-workbook rows on {day} are left out: {day} is the special"
                    f" shoot {specials[day].label!r}"
                ),
                details={"rows": n, "special_import_id": specials[day].import_id},
            )
        )
    special_rows = [
        row
        for source in specials.values()
        for row in load_staged_scores(session, source.import_id)
    ]
    kept = [row for row in weekly if row.event_date not in specials]
    return [*kept, *special_rows], {row.name_key for row in special_rows}
```

4. In `_live_rounds`, replace the signature

```python
def _live_rounds(
    session: Session,
    staged: list[StagedScore],
    rules: ActiveRules,
    merges: dict[int, int],
    issues: list[DataIssue],
) -> list[_LiveRound]:
```

with

```python
def _live_rounds(
    session: Session,
    staged: list[StagedScore],
    rules: ActiveRules,
    merges: dict[int, int],
    issues: list[DataIssue],
    special_keys: AbstractSet[str] = frozenset(),
) -> list[_LiveRound]:
```

and replace

```python
    shooter_ids: dict[str, int] = {}
    for name_key in sorted({row.name_key for _, row in visible}):
        shooter_id = resolve_shooter(session, names[name_key], first_dates[name_key])
        shooter_ids[name_key] = merges.get(shooter_id, shooter_id)
```

with

```python
    # A name key on a special sheet with an alias_name rule goes to that rule's shooter
    # (Decision 15); every other key resolves exactly as before.
    ruled = alias_rule_targets(session) if special_keys else {}
    shooter_ids: dict[str, int] = {}
    for name_key in sorted({row.name_key for _, row in visible}):
        target = ruled.get(name_key) if name_key in special_keys else None
        shooter_id = (
            target
            if target is not None
            else resolve_shooter(session, names[name_key], first_dates[name_key])
        )
        shooter_ids[name_key] = merges.get(shooter_id, shooter_id)
```

5. In `_write_events`, replace

```python
    rules: ActiveRules,
    issues: list[DataIssue],
) -> int:
    n_rounds: dict[date, int] = defaultdict(int)
```

with

```python
    rules: ActiveRules,
    issues: list[DataIssue],
    specials: Mapping[date, SpecialSource] | None = None,
) -> int:
    specials = specials or {}
    n_rounds: dict[date, int] = defaultdict(int)
```

then replace

```python
        if d in rules.round_types:
            round_type, source = rules.round_types[d][1], "override"
        elif d in layouts:
```

with

```python
        special = specials.get(d)
        if d in rules.round_types:
            round_type, source = rules.round_types[d][1], "override"
        elif special is not None:
            round_type, source = RoundType.SPORTING, "none"  # Decision 16
        elif d in layouts:
```

and replace

```python
                "has_stations": d in layouts,
                "results_complete": complete,
            }
        )
```

with

```python
                "has_stations": d in layouts,
                "results_complete": complete,
                "kind": "regular" if special is None else "special",
                "label": None if special is None else special.label,
                "target_total": REGULAR_TARGETS if special is None else special.target_total,
            }
        )
```

6. In `_write_profiles`, replace

```python
def _write_profiles(
    session: Session, rounds: list[_LiveRound], rules: ActiveRules, merges: dict[int, int]
) -> int:
```

with

```python
def _write_profiles(
    session: Session,
    rounds: list[_LiveRound],
    rules: ActiveRules,
    merges: dict[int, int],
    special_dates: AbstractSet[date] = frozenset(),
) -> int:
```

and replace

```python
                "n_rounds": len(own),
```

with

```python
                # Sundays shot count every appearance; rounds count scored (regular) rounds only
                "n_rounds": sum(1 for r in own if r.row.event_date not in special_dates),
```

In `backend/src/sunday_clays/domain/imports.py` (`_scores_station_findings`), replace

```python
        .join(ImportStationSheet, ImportStationSheet.id == StationHit.sheet_id)
        .group_by(StationHit.event_date, StationHit.entry_row, StationHit.name_key)
```

with

```python
        .join(ImportStationSheet, ImportStationSheet.id == StationHit.sheet_id)
        .join(Import, Import.id == ImportStationSheet.import_id)
        .where(Import.kind == FileKind.STATIONS.value)  # a special Sunday's sheet is its own
        .group_by(StationHit.event_date, StationHit.entry_row, StationHit.name_key)
```

- [ ] **Step 5: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/domain tests/integration/special/test_special_world.py`
Expected: all pass, including the existing rebuild goldens (`rebuild_events.json`), idempotence and concurrency tests: regular Sundays get `kind = 'regular'`, `label = NULL`, `target_total = 50` and nothing else changes.

- [ ] **Step 6: Gates and the full backend suite with coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest -q --cov --cov-branch`
Expected: all green, coverage at or above 90% lines and branches. The special world adds one fixture build (Decision 23). Note in the PR how long `fx_special_engine` took to build (`--durations=5` shows it).

- [ ] **Step 7: Commit**

```bash
git add backend/src/sunday_clays/domain/identity.py backend/src/sunday_clays/domain/rebuild.py backend/src/sunday_clays/domain/imports.py backend/tests/conftest.py backend/tests/integration/domain/test_rebuild_special.py backend/tests/integration/special/test_special_world.py
git commit -m "feat(special): special Sundays in the live tables and the fx_special world (Plan 17 T2)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The frames seam, the streak rule and the raw-SQL readers

One filter per seam (Decision 6): the score frames return regular Sundays only; two appearance frames and two display frames are added; `streaks()` learns the special-Sunday rule; every raw-SQL reader that bypasses the frames filters too. Each family gets a no-leak test that compares the `fx_special` world with `fx`.

**Files:**
- Modify: `backend/src/sunday_clays/analytics/frames.py`
- Modify: `backend/src/sunday_clays/analytics/streaks.py`
- Modify: `backend/src/sunday_clays/analytics/stations.py`, `analytics/achievements/context.py` (only `_STATION_SQL`), `analytics/insights/store.py` (only `_STATION_SUNDAYS_SQL`), `analytics/weather_effects.py`, `analytics/predictions.py`
- Modify: `backend/tests/unit/analytics_core/test_held_streaks.py`, `backend/tests/unit/analytics_core/test_frame_helpers.py`
- Create: `backend/tests/integration/special/test_special_frames.py`

**Interfaces:**
- Consumes: Task 2's `fx_special_session`; `fx_session`; `analytics.cache.clear_cache`.
- Produces (Tasks 4, 5 and 6 rely on these):
  - `frames.EVENT_KIND_REGULAR = "regular"`, `EVENT_KIND_SPECIAL = "special"`, `REGULAR_TARGETS = 50`.
  - `frames.load_rounds`, `load_events`, `load_station_hits`: regular Sundays only (same columns as before).
  - `frames.CALENDAR_COLUMNS = (*EVENT_COLUMNS, "kind", "label", "target_total")`; `load_calendar(session)`.
  - `frames.APPEARANCE_COLUMNS = ("shooter_id", "event_date", "kind", "round_type", "display_name", "shooter_status", "name_key", "held")`; `load_appearances(session)`.
  - `frames.SPECIAL_ROUND_COLUMNS = ("round_id", "event_date", "shooter_id", "name_key", "display_name", "shooter_status", "ordinal", "score", "label", "target_total")`; `load_special_rounds(session)`; `load_special_station_hits(session)` (`STATION_HIT_COLUMNS`).
  - `frames.appearances_from_rounds(rounds) -> DataFrame[APPEARANCE_COLUMNS]` (all `regular`); `frames.calendar_from_events(events) -> DataFrame` (adds `kind='regular'`, `label=None`, `target_total=50`).
  - `streaks(rounds_or_appearances, events_or_calendar, as_of)`: unchanged signature; honours a `kind` column when present (Decision 9).

- [ ] **Step 1: Write the failing streak and helper tests**

Append to `backend/tests/unit/analytics_core/test_held_streaks.py`:

```python
def _with_special(events: pd.DataFrame, *days: date) -> pd.DataFrame:
    calendar = frames.calendar_from_events(events)
    calendar.loc[calendar["event_date"].isin(days), "kind"] = frames.EVENT_KIND_SPECIAL
    return calendar


def test_a_special_sunday_extends_the_run_of_everyone_who_came(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = _with_special(make_events(W[:4]), W[2])
    rounds = make_rounds([(W[0], 1, 30), (W[1], 1, 30), (W[2], 1, 55), (W[3], 1, 30)])

    assert _by_shooter(streaks(rounds, events, None)) == {1: (4, 4)}


def test_a_special_sunday_never_breaks_the_run_of_anyone_who_skipped_it(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = _with_special(make_events(W[:4]), W[2])
    rounds = make_rounds([(W[0], 2, 30), (W[1], 2, 30), (W[3], 2, 30), (W[2], 1, 40)])

    assert _by_shooter(streaks(rounds, events, None)) == {1: (0, 1), 2: (3, 3)}


def test_a_special_latest_sunday_does_not_end_a_current_run(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = _with_special(make_events(W[:4]), W[3])
    rounds = make_rounds([(W[1], 1, 30), (W[2], 1, 30), (W[1], 2, 30), (W[2], 2, 30), (W[3], 2, 50)])

    assert _by_shooter(streaks(rounds, events, None)) == {1: (2, 2), 2: (3, 3)}


def test_a_missed_regular_sunday_still_breaks_a_run_through_a_special_one(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = _with_special(make_events(W[:5]), W[1])
    rounds = make_rounds([(W[0], 1, 30), (W[1], 1, 50), (W[3], 1, 30), (W[4], 1, 30)])

    assert _by_shooter(streaks(rounds, events, None)) == {1: (2, 2)}
```

and add `from sunday_clays.analytics import frames` to its imports.

Append to `backend/tests/unit/analytics_core/test_frame_helpers.py`:

```python
def test_appearances_from_rounds_is_one_regular_row_per_shooter_and_day(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d1, d2 = date(2026, 9, 6), date(2026, 9, 13)
    rounds = make_rounds([(d2, 1, 30), (d1, 1, 40), (d1, 1, 35), (d1, 2, 20)])

    out = frames.appearances_from_rounds(rounds)

    assert list(out.columns) == list(frames.APPEARANCE_COLUMNS)
    assert [(r.event_date, r.shooter_id, r.kind) for r in out.itertuples()] == [
        (d1, 1, "regular"),
        (d1, 2, "regular"),
        (d2, 1, "regular"),
    ]
    assert out["shooter_id"].dtype == "int64"
    assert out["held"].tolist() == [True, True, True]
    empty = frames.appearances_from_rounds(rounds.iloc[0:0])
    assert list(empty.columns) == list(frames.APPEARANCE_COLUMNS)
    assert empty.empty


def test_calendar_from_events_marks_every_sunday_regular_with_fifty_targets(
    make_events: Callable[..., pd.DataFrame],
) -> None:
    out = frames.calendar_from_events(make_events([date(2026, 9, 6), date(2026, 9, 13)]))

    assert out["kind"].tolist() == ["regular", "regular"]
    assert out["label"].tolist() == [None, None]
    assert out["target_total"].tolist() == [50, 50]
```

(Add `from collections.abc import Callable`, `from datetime import date` and `import pandas as pd` to that module if missing.)

- [ ] **Step 2: Write the failing no-leak tests**

Create `backend/tests/integration/special/test_special_frames.py`:

```python
"""No leak at the frames seam and the raw-SQL readers (Plan 17 Task 3, Review Focus 1).

Every score frame of the special world must equal the regular world's: same rounds, metrics,
ratings, events and station hits. Round ids differ between the worlds (each rebuild renumbers),
so they are dropped before comparing.
"""

from collections.abc import Callable
from datetime import date
from typing import Any

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames, predictions, weather_effects
from sunday_clays.analytics.achievements.context import load_station_entries
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.insights.store import readiness_from_db
from sunday_clays.analytics.stations import load_station_frame

SPECIAL = date(2026, 9, 20)
SCORES = {
    "Hadley, Ike": 55,
    "Kaplan, Noel": 51,
    "Devlin, Sid": 48,
    "Abernathy, Preston": 44,
    "Kim, Pat": 39,
}


def _both(fn: Callable[[Session], Any], base: Session, special: Session) -> tuple[Any, Any]:
    clear_cache()
    left = fn(base)
    clear_cache()
    return left, fn(special)


def _norm(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    out = df.drop(columns=[c for c in ("round_id",) if c in df.columns])
    return out.sort_values(keys, kind="mergesort").reset_index(drop=True)


SCORE_FRAMES = [
    (frames.load_rounds, ["event_date", "shooter_id", "name_key", "ordinal"]),
    (frames.load_events, ["event_date"]),
    (frames.load_station_hits, ["event_date", "entry_row", "station_label"]),
    (frames.load_rating_history, ["shooter_id", "event_date"]),
    (load_station_frame, ["event_date", "entry_row", "station_label"]),
    (load_station_entries, ["event_date", "entry_row", "station_label"]),
    (weather_effects.load_weather_events, ["event_date"]),
]


@pytest.mark.parametrize(
    ("loader", "keys"),
    SCORE_FRAMES,
    ids=["rounds", "events", "station_hits", "ratings", "stations_page", "ach_stations", "weather"],
)
def test_special_world_frames_match_the_regular_world(
    loader: Callable[[Session], pd.DataFrame],
    keys: list[str],
    fx_session: Session,
    fx_special_session: Session,
) -> None:
    base, special = _both(loader, fx_session, fx_special_session)

    pd.testing.assert_frame_equal(_norm(base, keys), _norm(special, keys))


def test_no_score_frame_holds_a_score_above_fifty(fx_special_session: Session) -> None:
    clear_cache()
    assert frames.load_rounds(fx_special_session)["score"].max() <= 50
    assert SPECIAL not in set(frames.load_rounds(fx_special_session)["event_date"])
    assert SPECIAL not in set(frames.load_events(fx_special_session)["event_date"])
    assert SPECIAL not in set(frames.load_station_hits(fx_special_session)["event_date"])


def test_the_calendar_is_the_events_plus_the_special_sunday(
    fx_session: Session, fx_special_session: Session
) -> None:
    base, calendar = _both(frames.load_calendar, fx_session, fx_special_session)

    assert list(calendar.columns) == list(frames.CALENDAR_COLUMNS)
    regular = calendar[calendar["kind"] == "regular"].reset_index(drop=True)
    pd.testing.assert_frame_equal(regular, base.reset_index(drop=True))
    (row,) = calendar[calendar["kind"] == "special"].to_dict("records")
    assert (row["event_date"], row["label"], row["target_total"]) == (SPECIAL, "Three Clay Shoot", 60)
    assert (row["n_shooters"], row["has_scores"], row["results_complete"]) == (5, True, True)
    assert pd.isna(row["median"]) and pd.isna(row["top_score"]) and pd.isna(row["difficulty"])
    assert calendar["target_total"].dtype == "int64"


def test_appearances_add_one_special_row_per_shooter_who_came(
    fx_session: Session, fx_special_session: Session
) -> None:
    base, appearances = _both(frames.load_appearances, fx_session, fx_special_session)

    assert list(appearances.columns) == list(frames.APPEARANCE_COLUMNS)
    regular = appearances[appearances["kind"] == "regular"].reset_index(drop=True)
    pd.testing.assert_frame_equal(regular, base.reset_index(drop=True))
    special = appearances[appearances["kind"] == "special"]
    assert set(special["event_date"]) == {SPECIAL}
    assert set(special["display_name"]) == set(SCORES)
    assert special["held"].all()
    clear_cache()
    rounds = frames.load_rounds(fx_session)
    implied = frames.appearances_from_rounds(rounds).reset_index(drop=True)
    pd.testing.assert_frame_equal(implied, base.reset_index(drop=True))


def test_special_rounds_and_station_hits_are_the_special_sunday_only(
    fx_session: Session, fx_special_session: Session
) -> None:
    clear_cache()
    assert frames.load_special_rounds(fx_session).empty
    assert frames.load_special_station_hits(fx_session).empty
    clear_cache()
    rounds = frames.load_special_rounds(fx_special_session)
    assert list(rounds.columns) == list(frames.SPECIAL_ROUND_COLUMNS)
    assert dict(zip(rounds["display_name"], rounds["score"], strict=True)) == SCORES
    assert list(rounds["score"]) == sorted(SCORES.values(), reverse=True)
    assert set(rounds["label"]) == {"Three Clay Shoot"}
    assert set(rounds["target_total"]) == {60}
    hits = frames.load_special_station_hits(fx_special_session)
    assert list(hits.columns) == list(frames.STATION_HIT_COLUMNS)
    assert len(hits) == 50
    assert set(hits["target_count"]) == {6}
    assert set(hits["round_id"].astype(int)) == set(rounds["round_id"])


def test_the_station_readiness_count_skips_the_special_sunday(
    fx_session: Session, fx_special_session: Session
) -> None:
    base, special = _both(readiness_from_db, fx_session, fx_special_session)
    assert special.station_sundays == base.station_sundays


def test_predictions_and_the_club_weather_model_are_unchanged(
    fx_session: Session, fx_special_session: Session
) -> None:
    target = date(2026, 10, 4)
    base, special = _both(
        lambda s: predictions.next_predictions(s, target, None, None), fx_session, fx_special_session
    )
    assert special == base
    base_model, special_model = _both(
        lambda s: weather_effects.club_regression(s, (), weather_effects.COVARIATES),
        fx_session,
        fx_special_session,
    )
    assert special_model == base_model
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/unit/analytics_core/test_held_streaks.py tests/unit/analytics_core/test_frame_helpers.py tests/integration/special/test_special_frames.py`
Expected: FAIL. `frames.calendar_from_events` / `EVENT_KIND_SPECIAL` / `appearances_from_rounds` / `load_calendar` do not exist; every `SCORE_FRAMES` case differs (the special world's rounds hold the five 2026-09-20 rounds, and s10/s30 metrics and ratings moved with them); `predictions` and the weather model see the extra Sunday.

- [ ] **Step 4: Write the frames seam**

In `backend/src/sunday_clays/analytics/frames.py`:

1. Below `UNSPECIFIED_GAUGE = "unspecified"`, add:

```python
EVENT_KIND_REGULAR = "regular"
EVENT_KIND_SPECIAL = "special"  # Plan 17: a special Sunday counts only as an appearance
REGULAR_TARGETS = 50
```

2. Below `SHOOTER_COLUMNS = (...)`, add:

```python
CALENDAR_COLUMNS: tuple[str, ...] = (*EVENT_COLUMNS, "kind", "label", "target_total")
APPEARANCE_COLUMNS: tuple[str, ...] = (
    "shooter_id",
    "event_date",
    "kind",
    "round_type",
    "display_name",
    "shooter_status",
    "name_key",
    "held",
)
SPECIAL_ROUND_COLUMNS: tuple[str, ...] = (
    "round_id",
    "event_date",
    "shooter_id",
    "name_key",
    "display_name",
    "shooter_status",
    "ordinal",
    "score",
    "label",
    "target_total",
)
```

3. Replace the three SQL constants `_ROUNDS_SQL`, `_EVENTS_SQL` and `_STATION_HITS_SQL` (from `_ROUNDS_SQL = """` down to the `"""` that closes `_STATION_HITS_SQL`) with:

```python
# Plan 17: every score frame reads regular Sundays only (`WHERE e.kind = 'regular'`); the
# appearance frames below are the only readers that see special Sundays.
_ROUNDS_SQL = """
SELECT r.id AS round_id, r.event_date, r.shooter_id, r.name_key, p.display_name,
       r.ordinal, r.score, r.gauge_class, r.status, p.status AS shooter_status,
       e.round_type, m.field_median, m.adjusted, m.event_rank, m.is_best_round,
       m.percentile, m.expected, m.residual, m.mu_before, m.mu_after, w.temp_f,
       w.apparent_f, w.precip_in, w.wind_mph, w.gust_mph, w.wind_dir_deg, w.cloud_pct,
       w.condition, e.results_complete AS held
FROM rounds r
JOIN events e ON e.event_date = r.event_date
JOIN shooter_profiles p ON p.shooter_id = r.shooter_id
LEFT JOIN round_metrics m ON m.round_id = r.id
LEFT JOIN event_weather w ON w.event_date = r.event_date
WHERE e.kind = 'regular'
ORDER BY r.event_date, r.shooter_id, r.name_key, r.ordinal
"""
_EVENTS_SQL = """
SELECT e.event_date, e.round_type, e.round_type_source, e.head_count, e.n_rounds,
       e.n_shooters, e.has_scores, e.has_stations, e.results_complete, m.n, m.median,
       m.mean, m.stdev, m.top_score, m.difficulty, w.temp_f, w.apparent_f, w.precip_in,
       w.wind_mph, w.gust_mph, w.wind_dir_deg, w.cloud_pct, w.humidity_pct,
       w.pressure_hpa, w.condition
FROM events e
LEFT JOIN event_metrics m ON m.event_date = e.event_date
LEFT JOIN event_weather w ON w.event_date = e.event_date
WHERE e.kind = 'regular'
ORDER BY e.event_date
"""
_CALENDAR_SQL = """
SELECT e.event_date, e.round_type, e.round_type_source, e.head_count, e.n_rounds,
       e.n_shooters, e.has_scores, e.has_stations, e.results_complete, m.n, m.median,
       m.mean, m.stdev, m.top_score, m.difficulty, w.temp_f, w.apparent_f, w.precip_in,
       w.wind_mph, w.gust_mph, w.wind_dir_deg, w.cloud_pct, w.humidity_pct,
       w.pressure_hpa, w.condition, e.kind, e.label, e.target_total
FROM events e
LEFT JOIN event_metrics m ON m.event_date = e.event_date
LEFT JOIN event_weather w ON w.event_date = e.event_date
ORDER BY e.event_date
"""
_STATION_HITS_SQL = """
SELECT h.event_date, h.station_no, h.station_label, l.target_count, h.sheet_id, h.entry_row,
       h.name_key, h.shooter_id, h.round_id, h.hits, e.round_type
FROM station_hits h
JOIN station_layouts l ON l.event_date = h.event_date AND l.station_label = h.station_label
JOIN events e ON e.event_date = h.event_date
WHERE e.kind = 'regular'
ORDER BY h.event_date, h.entry_row, h.station_no, h.station_label
"""
_SPECIAL_STATION_HITS_SQL = """
SELECT h.event_date, h.station_no, h.station_label, l.target_count, h.sheet_id, h.entry_row,
       h.name_key, h.shooter_id, h.round_id, h.hits, e.round_type
FROM station_hits h
JOIN station_layouts l ON l.event_date = h.event_date AND l.station_label = h.station_label
JOIN events e ON e.event_date = h.event_date
WHERE e.kind = 'special'
ORDER BY h.event_date, h.entry_row, h.station_no, h.station_label
"""
_APPEARANCES_SQL = """
SELECT r.shooter_id, r.event_date, e.kind, e.round_type, p.display_name,
       p.status AS shooter_status, min(r.name_key) AS name_key, e.results_complete AS held
FROM rounds r
JOIN events e ON e.event_date = r.event_date
JOIN shooter_profiles p ON p.shooter_id = r.shooter_id
GROUP BY r.shooter_id, r.event_date, e.kind, e.round_type, p.display_name, p.status,
         e.results_complete
ORDER BY r.event_date, r.shooter_id
"""
_SPECIAL_ROUNDS_SQL = """
SELECT r.id AS round_id, r.event_date, r.shooter_id, r.name_key, p.display_name,
       p.status AS shooter_status, r.ordinal, r.score, e.label, e.target_total
FROM rounds r
JOIN events e ON e.event_date = r.event_date
JOIN shooter_profiles p ON p.shooter_id = r.shooter_id
WHERE e.kind = 'special'
ORDER BY r.event_date, r.score DESC, p.display_name, r.ordinal
"""
```

4. Replace `load_events` and `load_station_hits` with:

```python
_EVENT_FLOATS: tuple[str, ...] = (
    "head_count",
    "n",
    "median",
    "mean",
    "stdev",
    "top_score",
    "difficulty",
    "temp_f",
    "apparent_f",
    "precip_in",
    "wind_mph",
    "gust_mph",
    "wind_dir_deg",
    "cloud_pct",
    "humidity_pct",
    "pressure_hpa",
)
_EVENT_BOOLS: tuple[str, ...] = ("has_scores", "has_stations", "results_complete")


@cached_by_data_version
def load_events(session: Session) -> pd.DataFrame:
    """Each regular `events` row plus event_metrics/event_weather columns (NaN if absent)."""
    return _frame(
        session,
        _EVENTS_SQL,
        EVENT_COLUMNS,
        ints=("n_rounds", "n_shooters"),
        floats=_EVENT_FLOATS,
        bools=_EVENT_BOOLS,
    )


@cached_by_data_version
def load_calendar(session: Session) -> pd.DataFrame:
    """Every Sunday, special ones included (Plan 17): load_events' columns plus kind, label and
    target_total. For appearance consumers (turnout, calendars, streaks); a special row has no
    metrics."""
    return _frame(
        session,
        _CALENDAR_SQL,
        CALENDAR_COLUMNS,
        ints=("n_rounds", "n_shooters", "target_total"),
        floats=_EVENT_FLOATS,
        bools=_EVENT_BOOLS,
    )


@cached_by_data_version
def load_appearances(session: Session) -> pd.DataFrame:
    """One row per shooter per Sunday shot, special Sundays included (Plan 17)."""
    return _frame(session, _APPEARANCES_SQL, APPEARANCE_COLUMNS, ints=("shooter_id",), bools=("held",))


@cached_by_data_version
def load_special_rounds(session: Session) -> pd.DataFrame:
    """The rounds of special Sundays only (Plan 17), best first: for display, never for stats."""
    return _frame(
        session,
        _SPECIAL_ROUNDS_SQL,
        SPECIAL_ROUND_COLUMNS,
        ints=("round_id", "shooter_id", "ordinal", "score", "target_total"),
    )


def _station_frame(session: Session, sql: str) -> pd.DataFrame:
    df = _frame(
        session,
        sql,
        STATION_HIT_COLUMNS,
        ints=("station_no", "target_count", "sheet_id", "entry_row", "hits"),
        nullable_ints=("shooter_id", "round_id"),
    )
    df["station_label"] = df["station_label"].astype(str)  # text dtype, empty or not
    return df


@cached_by_data_version
def load_station_hits(session: Session) -> pd.DataFrame:
    """Regular Sundays' station_hits with the station's target_count and the round_type."""
    return _station_frame(session, _STATION_HITS_SQL)


@cached_by_data_version
def load_special_station_hits(session: Session) -> pd.DataFrame:
    """Special Sundays' station grids (Plan 17): for the Sunday page only."""
    return _station_frame(session, _SPECIAL_STATION_HITS_SQL)


def appearances_from_rounds(rounds: pd.DataFrame) -> pd.DataFrame:
    """The appearance frame a rounds frame implies: its Sundays shot, all regular (Plan 17).

    Equal to load_appearances when no special Sunday exists; callers and unit-test worlds that
    hold only rounds use it.
    """
    if rounds.empty:
        return pd.DataFrame(
            {
                c: pd.Series(dtype="int64" if c == "shooter_id" else "bool" if c == "held" else object)
                for c in APPEARANCE_COLUMNS
            }
        )
    days = rounds.groupby(["shooter_id", "event_date"], as_index=False, sort=False).agg(
        round_type=("round_type", "first"),
        display_name=("display_name", "first"),
        shooter_status=("shooter_status", "first"),
        name_key=("name_key", "min"),
        held=("held", "first"),
    )
    days["kind"] = EVENT_KIND_REGULAR
    days["shooter_id"] = days["shooter_id"].astype("int64")
    days["held"] = days["held"].eq(True)
    ordered = days.sort_values(["event_date", "shooter_id"], kind="mergesort")
    return ordered.reset_index(drop=True)[list(APPEARANCE_COLUMNS)]


def calendar_from_events(events: pd.DataFrame) -> pd.DataFrame:
    """The calendar an events frame implies: every Sunday regular, 50 targets (Plan 17)."""
    out = events.copy()
    out["kind"] = EVENT_KIND_REGULAR
    out["label"] = None
    out["target_total"] = REGULAR_TARGETS
    return out
```

5. Change `load_rounds`' docstring first line to `"""One row per live round of a regular Sunday, with metrics, weather and derived gauge/held.`.

- [ ] **Step 5: Write the streak rule**

Replace `backend/src/sunday_clays/analytics/streaks.py` from `def streaks(` to the end with:

```python
def _special_dates(events: pd.DataFrame) -> set[date]:
    """Dates of special Sundays (Plan 17); none when the frame has no `kind` column."""
    if "kind" not in events.columns:
        return set()
    return set(events.loc[events["kind"].eq("special"), "event_date"])


def streaks(rounds: pd.DataFrame, events: pd.DataFrame, as_of: date | None) -> pd.DataFrame:
    """Consecutive held events attended, per shooter with a round on/before `as_of`.

    Non-held dates are skipped: they neither extend nor break a streak. A special Sunday (an
    events `kind` of 'special', Plan 17) extends the run of everyone who came and is skipped for
    everyone else: two attended dates are consecutive when no *regular* held date lies between
    them. current_streak is the run whose last date has no regular held date after it (0 if the
    shooter missed the latest regular held date). `rounds` may be an appearance frame: only
    shooter_id and event_date are read.
    """
    held = held_event_dates(events, as_of)
    special = _special_dates(events)
    position = {d: i for i, d in enumerate(held)}
    # regular_before[k]: regular held dates among held[:k]
    regular_before = list(itertools.accumulate((d not in special for d in held), initial=0))
    upto = rounds if as_of is None else rounds.loc[rounds["event_date"] <= as_of]
    attended: dict[int, set[int]] = {int(s): set() for s in upto["shooter_id"].unique()}
    for shooter_id, event_date in zip(upto["shooter_id"], upto["event_date"], strict=True):
        if event_date in position:
            attended[int(shooter_id)].add(position[event_date])
    total_regular = regular_before[-1]
    rows: list[tuple[int, int, int]] = []
    for shooter_id in sorted(attended):
        longest = run = 0
        previous: int | None = None
        for i in sorted(attended[shooter_id]):
            gapless = previous is not None and regular_before[i] == regular_before[previous + 1]
            run = run + 1 if gapless else 1
            longest = max(longest, run)
            previous = i
        current = (
            run if previous is not None and regular_before[previous + 1] == total_regular else 0
        )
        rows.append((shooter_id, current, longest))
    return pd.DataFrame(rows, columns=list(STREAK_COLUMNS)).astype("int64")
```

and add `import itertools` at the top of the module.

- [ ] **Step 6: Filter the raw-SQL readers**

`backend/src/sunday_clays/analytics/stations.py`, in `_FRAME_SQL`, replace

```python
    LEFT JOIN shooter_profiles p ON p.shooter_id = h.shooter_id
    ORDER BY h.event_date, h.entry_row, h.station_no, h.station_label
```

with

```python
    LEFT JOIN shooter_profiles p ON p.shooter_id = h.shooter_id
    WHERE e.kind = 'regular'
    ORDER BY h.event_date, h.entry_row, h.station_no, h.station_label
```

`backend/src/sunday_clays/analytics/achievements/context.py`, in `_STATION_SQL`, replace

```python
    FROM station_hits h
    JOIN station_layouts l ON l.event_date = h.event_date AND l.station_label = h.station_label
    ORDER BY h.event_date, h.entry_row, h.station_no, h.station_label
```

with

```python
    FROM station_hits h
    JOIN station_layouts l ON l.event_date = h.event_date AND l.station_label = h.station_label
    JOIN events e ON e.event_date = h.event_date
    WHERE e.kind = 'regular'
    ORDER BY h.event_date, h.entry_row, h.station_no, h.station_label
```

`backend/src/sunday_clays/analytics/insights/store.py`, replace

```python
    "JOIN events e ON e.event_date = h.event_date"
)
```

with

```python
    "JOIN events e ON e.event_date = h.event_date WHERE e.kind = 'regular'"
)
```

`backend/src/sunday_clays/analytics/weather_effects.py`, in `_WEATHER_EVENTS_SQL`, replace

```python
LEFT JOIN event_metrics AS m ON m.event_date = e.event_date
ORDER BY e.event_date
"""
_EVENT_COLUMNS: Final[tuple[str, ...]] = (
```

with

```python
LEFT JOIN event_metrics AS m ON m.event_date = e.event_date
WHERE e.kind = 'regular'
ORDER BY e.event_date
"""
_EVENT_COLUMNS: Final[tuple[str, ...]] = (
```

`backend/src/sunday_clays/analytics/predictions.py`, replace

```python
    rows = session.execute(text("SELECT event_date, has_scores FROM events")).all()
```

with

```python
    rows = session.execute(
        text("SELECT event_date, has_scores FROM events WHERE kind = 'regular'")
    ).all()
```

- [ ] **Step 7: Run them to verify they pass**

Run: `cd backend && uv run ruff format src tests && uv run pytest -q tests/unit/analytics_core tests/integration/special tests/integration/analytics_core/test_frame_loaders.py`
Expected: all pass.

- [ ] **Step 8: Gates and the full backend suite with coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest -q --cov --cov-branch`
Expected: all green. Every golden (`insights_counts.json`, the achievement goldens, `rebuild_events.json`) passes untouched: the fixture world has no special Sunday, so each frame returns what it did before.

- [ ] **Step 9: Commit**

```bash
git add backend/src/sunday_clays/analytics/frames.py backend/src/sunday_clays/analytics/streaks.py backend/src/sunday_clays/analytics/stations.py backend/src/sunday_clays/analytics/achievements/context.py backend/src/sunday_clays/analytics/insights/store.py backend/src/sunday_clays/analytics/weather_effects.py backend/src/sunday_clays/analytics/predictions.py backend/tests/unit/analytics_core/test_held_streaks.py backend/tests/unit/analytics_core/test_frame_helpers.py backend/tests/integration/special/test_special_frames.py
git commit -m "feat(special): regular-only score frames, appearance frames and the streak rule (Plan 17 T3)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Appearance trophies and appearance insights

Trophies and insights read the regular frames since Task 3, so every score trophy and score insight already ignores the special Sunday. This task gives the attendance trophies, the attendance insights and the club turnout and newcomer insights the appearance frames, so a special Sunday counts for them (Decisions 7, 9, 10, 11, 12).

**Files:**
- Modify: `backend/src/sunday_clays/analytics/achievements/context.py`, `analytics/achievements/participation.py`
- Modify: `backend/src/sunday_clays/analytics/insights/context.py`, `insights/attendance.py`, `insights/milestones.py`, `insights/records.py`, `insights/anchors.py`, `insights/trophies.py`, `insights/club.py`, `insights/community.py`
- Modify: `backend/src/sunday_clays/analytics/steps/s60_insights.py`
- Modify: `backend/tests/unit/analytics/achievements/conftest.py`, `tests/unit/analytics/achievements/test_ach_participation.py`
- Modify: `backend/tests/unit/analytics/insights/conftest.py`, `tests/unit/analytics/insights/test_kinds_attendance.py`, `tests/unit/analytics/insights/test_kinds_milestones.py`, `tests/unit/analytics/insights/test_kinds_records.py`, `tests/unit/analytics/insights/test_kinds_club.py`, `tests/unit/analytics/insights/test_kinds_community.py`
- Create: `backend/tests/integration/special/test_special_trophies_insights.py`

**Interfaces:**
- Consumes: Task 3's `frames.{load_appearances, load_calendar, appearances_from_rounds, calendar_from_events, APPEARANCE_COLUMNS, CALENDAR_COLUMNS, EVENT_KIND_SPECIAL}` and the streak rule; `fx_session`, `fx_special_session`.
- Produces:
  - `AchContext.appearances`, `AchContext.calendar` (with `event_ts`); `AchContext.from_frames(..., appearances=None, calendar=None)`; `AchContext.attendance_days` (shooter_id, event_ts, event_date, special, n_events, prev_ts, best_round_id: Int64, `<NA>` on a special Sunday); `AchContext.calendar_held_dates()`; `streaks_at` reads appearances and calendar.
  - `InsightFrames.appearances`, `.calendar`, `.special_days`, `.appearance_dates`; `from_frames(..., appearances=None, calendar=None)`; `appearances_through(sid, day) -> int`, `specials_through(sid, day) -> tuple[date, ...]`, `no_held_between(a, b) -> bool`; `Day.k` counts special Sundays.
  - `insights.club.special_turnout(fr, start, end) -> list[tuple[date, float]]` (every held special Sunday in the window: its head count, else its shooters); `insights.club.head_counts` includes those Sundays.
  - Test builders: `CtxBuilder.special(shooter_id, day)`, `World.special(sid, day, *, heads=None)`.

- [ ] **Step 1: Teach the test builders special Sundays**

In `backend/tests/unit/analytics/achievements/conftest.py`, replace

```python
from sunday_clays.analytics.frames import EVENT_COLUMNS, ROUND_COLUMNS
```

with

```python
from sunday_clays.analytics.frames import (
    APPEARANCE_COLUMNS,
    CALENDAR_COLUMNS,
    EVENT_COLUMNS,
    ROUND_COLUMNS,
    appearances_from_rounds,
    calendar_from_events,
)
```

replace

```python
        self._stations: list[dict[str, Any]] = []
        self._history: list[dict[str, Any]] = []

    def round(
```

with

```python
        self._stations: list[dict[str, Any]] = []
        self._history: list[dict[str, Any]] = []
        self._specials: list[tuple[int, date]] = []

    def special(self, shooter_id: int, event_date: date) -> CtxBuilder:
        """A special Sunday shot (Plan 17): an appearance only, never a round or a regular event."""
        self._specials.append((shooter_id, event_date))
        return self

    def round(
```

and replace

```python
    def build(self) -> AchContext:
        events = self._events_frame()
        return AchContext.from_frames(
            rounds=self._rounds_frame(events),
            events=events,
            station_hits=self._stations_frame(),
            rating_history=pd.DataFrame(
                self._history, columns=["shooter_id", "event_date", "mu", "var"]
            ),
        )
```

with

```python
    def build(self) -> AchContext:
        events = self._events_frame()
        rounds = self._rounds_frame(events)
        return AchContext.from_frames(
            rounds=rounds,
            events=events,
            station_hits=self._stations_frame(),
            rating_history=pd.DataFrame(
                self._history, columns=["shooter_id", "event_date", "mu", "var"]
            ),
            appearances=self._appearances(rounds),
            calendar=self._calendar(events),
        )

    def _appearances(self, rounds: pd.DataFrame) -> pd.DataFrame:
        regular = appearances_from_rounds(rounds)
        if not self._specials:
            return regular
        special = pd.DataFrame(
            [
                {
                    "shooter_id": sid,
                    "event_date": day,
                    "kind": "special",
                    "round_type": "sporting",
                    "display_name": f"Shooter {sid}",
                    "shooter_status": "member",
                    "name_key": f"shooter {sid}",
                    "held": True,
                }
                for sid, day in self._specials
            ],
            columns=list(APPEARANCE_COLUMNS),
        )
        both = pd.concat([regular, special], ignore_index=True)
        return both.sort_values(["event_date", "shooter_id"], kind="mergesort").reset_index(
            drop=True
        )

    def _calendar(self, events: pd.DataFrame) -> pd.DataFrame:
        calendar = calendar_from_events(events)
        days = sorted({day for _, day in self._specials})
        if not days:
            return calendar
        rows: list[dict[str, Any]] = []
        for day in days:
            row: dict[str, Any] = dict.fromkeys(CALENDAR_COLUMNS, np.nan)
            n = sum(1 for _, d in self._specials if d == day)
            row.update(
                event_date=day,
                round_type="sporting",
                round_type_source="none",
                n_rounds=n,
                n_shooters=n,
                has_scores=True,
                has_stations=False,
                results_complete=True,
                condition=None,
                kind="special",
                label="Three Clay Shoot",
                target_total=60,
            )
            rows.append(row)
        both = pd.concat([calendar, pd.DataFrame(rows, columns=list(CALENDAR_COLUMNS))])
        return both.sort_values("event_date", kind="mergesort").reset_index(drop=True)
```

In `backend/tests/unit/analytics/insights/conftest.py`, add `from collections import Counter` to the imports, add `self._specials: list[tuple[int, date]] = []` and `self._special_heads: dict[date, int] = {}` at the end of `World.__init__`, add after `World.award`:

```python
    def special(self, sid: int, day: date, *, heads: int | None = None) -> World:
        """A special Sunday shot (Plan 17): an appearance only, never a round. `heads` is the
        Sunday's head count (default: none, as when the weekly workbook has no row for it)."""
        self._specials.append((sid, day))
        self._shooters.setdefault(sid, {})
        if heads is not None:
            self._special_heads[day] = heads
        return self
```

and replace the end of `World.frames`

```python
        return InsightFrames.from_frames(
            rounds=rounds,
            events=events,
            shooters=self._shooter_frame(rounds),
            rating=pd.DataFrame(self._ratings, columns=list(frames.RATING_COLUMNS)),
            stations=pd.DataFrame(self._stations, columns=list(frames.STATION_HIT_COLUMNS)),
            awards=pd.DataFrame(self._awards, columns=list(AWARD_COLUMNS)),
        )
```

with

```python
        appearances = frames.appearances_from_rounds(rounds)
        calendar = frames.calendar_from_events(events)
        if self._specials:
            names = self._names()
            extra = pd.DataFrame(
                [
                    {
                        "shooter_id": sid,
                        "event_date": day,
                        "kind": "special",
                        "round_type": "sporting",
                        "display_name": names[sid],
                        "shooter_status": "member",
                        "name_key": f"s{sid}",
                        "held": True,
                    }
                    for sid, day in self._specials
                ],
                columns=list(frames.APPEARANCE_COLUMNS),
            )
            appearances = (
                pd.concat([appearances, extra], ignore_index=True)
                .sort_values(["event_date", "shooter_id"], kind="mergesort")
                .reset_index(drop=True)
            )
            special_days = pd.DataFrame(
                [
                    {
                        **dict.fromkeys(frames.CALENDAR_COLUMNS, np.nan),
                        "event_date": day,
                        "head_count": self._special_heads.get(day, np.nan),
                        "round_type": "sporting",
                        "round_type_source": "none",
                        "n_rounds": n,
                        "n_shooters": n,
                        "has_scores": True,
                        "has_stations": False,
                        "results_complete": True,
                        "condition": None,
                        "kind": "special",
                        "label": "Three Clay Shoot",
                        "target_total": 60,
                    }
                    for day, n in sorted(Counter(day for _, day in self._specials).items())
                ],
                columns=list(frames.CALENDAR_COLUMNS),
            )
            calendar = (
                pd.concat([calendar, special_days], ignore_index=True)
                .sort_values("event_date", kind="mergesort")
                .reset_index(drop=True)
            )
        return InsightFrames.from_frames(
            rounds=rounds,
            events=events,
            shooters=self._shooter_frame(rounds),
            rating=pd.DataFrame(self._ratings, columns=list(frames.RATING_COLUMNS)),
            stations=pd.DataFrame(self._stations, columns=list(frames.STATION_HIT_COLUMNS)),
            awards=pd.DataFrame(self._awards, columns=list(AWARD_COLUMNS)),
            appearances=appearances,
            calendar=calendar,
        )
```

(`World.special` must not use a date that also has a regular Sunday; the tests below never do.)

- [ ] **Step 2: Write the failing trophy tests**

Append to `backend/tests/unit/analytics/achievements/test_ach_participation.py`:

```python
# ---- special Sundays (Plan 17): they count as Sundays shot, never as rounds ---------------


def special_ctx(b):
    """Shooter 1 shoots sun(0), the special sun(1) and sun(2); shooter 2 skips the special."""
    return (
        b()
        .round(1, sun(0), 30)
        .special(1, sun(1))
        .round(1, sun(2), 31)
        .round(2, sun(0), 40)
        .round(2, sun(2), 41)
        .build()
    )


def test_a_special_sunday_counts_toward_events_years_and_big_year(ctx_builder):
    ctx = special_ctx(ctx_builder)

    assert value_series("events", ctx, 1) == [1.0, 2.0, 3.0]
    assert value_series("events", ctx, 2) == [1.0, 2.0]
    assert value_series("big_year", ctx, 1) == [1.0, 2.0, 3.0]
    assert value_series("years_active", ctx, 1) == [1.0, 1.0, 1.0]


def test_iron_streak_runs_through_a_special_sunday_and_never_breaks_on_it(ctx_builder):
    ctx = special_ctx(ctx_builder)

    assert value_series("iron_streak", ctx, 1) == [1.0, 2.0, 3.0]
    assert value_series("iron_streak", ctx, 2) == [1.0, 2.0]


def test_score_trophies_ignore_the_special_sunday(ctx_builder):
    ctx = special_ctx(ctx_builder)

    assert value_series("clays_broken", ctx, 1) == [30.0, 61.0]
    assert value_series("clays_thrown", ctx, 1) == [50.0, 100.0]
    assert value_series("personal_bests", ctx, 1) == [0.0, 0.0]
    assert awards("doubleheader", ctx) == []


def test_new_year_goes_to_a_special_sunday_before_the_first_regular_one(ctx_builder):
    jan4, jan11, jan18 = date(2026, 1, 4), date(2026, 1, 11), date(2026, 1, 18)
    ctx = (
        ctx_builder()
        .special(1, jan4)
        .special(2, jan4)
        .round(1, jan11, 30)
        .round(3, jan11, 30)
        .special(4, jan18)
        .build()
    )

    found = sorted(
        (w.shooter_id, w.event_date, w.round_id is None)
        for w in registry.evaluate_one(registry.get("new_year"), ctx)
    )
    assert found == [(1, jan4, True), (2, jan4, True), (3, jan11, False)]


def test_welcome_back_and_the_anniversary_count_a_special_sunday(ctx_builder):
    d0 = date(2025, 1, 5)
    back, year_on = d0 + timedelta(weeks=29), d0 + timedelta(weeks=52)
    ctx = ctx_builder().round(1, d0, 30).special(1, back).special(1, year_on).build()

    (welcome,) = registry.evaluate_one(registry.get("welcome_back"), ctx)
    assert (welcome.event_date, welcome.round_id, welcome.details) == (
        back,
        None,
        {"days_away": 203},
    )
    assert awards("anniversary_1", ctx) == [(1, "anniversary_1", year_on)]


def test_perfect_month_counts_a_special_sunday_toward_the_three(ctx_builder):
    mar1, mar8, mar15, apr5 = date(2026, 3, 1), date(2026, 3, 8), date(2026, 3, 15), date(2026, 4, 5)
    ctx = (
        ctx_builder()
        .round(1, mar1, 30)
        .round(2, mar1, 30)
        .special(1, mar8)
        .round(1, mar15, 30)
        .round(2, mar15, 30)
        .round(3, apr5, 30)
        .build()
    )

    assert awards("perfect_month", ctx) == [(1, "perfect_month", apr5)]


@pytest.mark.parametrize("code", ["events", "iron_streak", "new_year", "perfect_month"])
def test_appearance_trophies_with_a_special_sunday_never_leak(ctx_builder, no_leak, code):
    no_leak(code, special_ctx(ctx_builder), sun(1))  # the fixture asserts full == sliced
```

- [ ] **Step 3: Write the failing insight tests**

Append to `backend/tests/unit/analytics/insights/test_kinds_attendance.py`:

```python
def test_attendance_streak_runs_through_a_special_sunday_and_never_breaks_on_it(
    make_world, sun, run
):
    world = make_world()
    for i in (0, 1, 3, 4, 5):
        world.crowd(sun(i), [30, 31]).round(1, sun(i), 30).round(2, sun(i), 30)
    world.special(1, sun(2))
    fr = world.frames()

    facts = {f.subject_id: f for f in run("pf.attendance-streak", fr) if f.anchor_date is None}
    assert (facts["1"].params["k"], facts["1"].params["start"]) == (6, sun(0))
    assert (facts["2"].params["k"], facts["2"].params["start"]) == (5, sun(0))
```

Append to `backend/tests/unit/analytics/insights/test_kinds_milestones.py`:

```python
def test_sunday_counts_include_special_sundays(make_world, sun, run):
    world = make_world()
    for i in range(24):
        world.crowd(sun(i), [30]).round(1, sun(i), 30)
    world.special(1, sun(24))  # Sunday 25 is special: no anchored milestone (Decision 11)
    world.crowd(sun(25), [30]).round(1, sun(25), 30)
    fr = world.frames()

    assert fr.histories[1][-1].k == 26
    assert fr.appearances_through(1, sun(25)) == 26
    assert fr.specials_through(1, sun(25)) == (sun(24),)
    assert not [
        f for f in run("pf.sunday-milestone", fr) if f.subject_id == "1" and f.anchor_date
    ]


def test_the_sundays_to_go_count_a_special_sunday_after_the_last_round(make_world, sun, run):
    world = make_world()
    for i in range(22):
        world.crowd(sun(i), [30]).round(1, sun(i), 30)
    world.special(1, sun(22))
    world.crowd(sun(23), [30])  # the latest Sunday; shooter 1 missed it
    fr = world.frames()

    (fact,) = [
        f for f in run("pf.sunday-milestone", fr) if f.subject_id == "1" and f.variant == "to_go"
    ]
    assert (fact.params["next"], fact.params["to_go"]) == (25, 2)
```

Append to `backend/tests/unit/analytics/insights/test_kinds_records.py`:

```python
def test_streak_chase_counts_a_special_sunday_in_the_run(make_world, sun, run):
    world = make_world()
    for i in [*range(7), *range(8, 15)]:  # 14 regular Sundays around the special sun(7)
        world.crowd(sun(i), [30]).round(1, sun(i), 30).round(2, sun(i), 30)
    world.special(1, sun(7))
    fr = world.frames()

    (fact,) = [f for f in run("rec.streak-chase", fr) if f.variant == "attendance"]
    # CHASE_RUN is 15: shooter 1 (14 regular + the special) is chasing; shooter 2 (14, never
    # broken by the special Sunday) is not yet.
    assert fact.params["record"] == 15
    assert fact.params["ids"] == [1]
```

Append to `backend/tests/unit/analytics/insights/test_kinds_club.py`:

```python
def test_turnout_trend_counts_a_special_sunday(make_world, run, sun):
    """Plan 17: a special Sunday's turnout is its head count, else the shooters on its sheet."""

    def frames_with(special):
        world = make_world()
        for i in [*range(8), *range(9, 16)]:  # sun(8) is left for the special Sunday
            world.sunday(sun(i), head_count=20 if i < 8 else 26).crowd(sun(i), [30])
        special(world)
        return world.frames()

    assert run("cl.turnout-trend", frames_with(lambda w: None)) == []  # 15 Sundays: too few
    by_sheet = frames_with(lambda w: [w.special(sid, sun(8)) for sid in range(1, 27)])
    (fact,) = run("cl.turnout-trend", by_sheet)
    assert (fact.variant, fact.params["recent"], fact.params["before"]) == ("recent", 26, 20)
    assert fact.params["start"] == sun(8)
    by_heads = frames_with(lambda w: w.special(1, sun(8), heads=26))  # 1 on the sheet, 26 came
    (fact,) = run("cl.turnout-trend", by_heads)
    assert (fact.params["recent"], fact.params["start"]) == (26, sun(8))
    assert club.special_turnout(by_heads, sun(0), sun(15)) == [(sun(8), 26.0)]
```

Append to `backend/tests/unit/analytics/insights/test_kinds_community.py`:

```python
def test_newcomers_count_a_first_sunday_at_a_special_shoot(make_world, run):
    """Plan 17: cohorts follow Sundays shot, like the /club "new" chart the fact links to."""
    days = sundays_of(2025, 3)
    world = make_world()
    for sid in range(1, 10):
        world.round(sid, days[0], 30)
    for sid in range(1, 4):
        world.round(sid, days[2], 30)
    assert run("cl.newcomers", world.frames()) == []  # 9 new: under NEWCOMERS_MIN
    world.special(10, days[1])  # shooter 10's only Sunday is the special shoot
    (fact,) = run("cl.newcomers", world.frames())
    assert (fact.params["n"], fact.params["back"], fact.params["year"]) == (10, 3, 2025)


def test_year_wrap_counts_a_special_sunday(make_world, run):
    """Plan 17: the special Sunday is one of the year's Sundays, can be the busiest, and its new
    shooters are first-timers; the round count stays the scored rounds."""
    days = sundays_of(2024, 30)
    world = make_world()
    for day in days[:15] + days[16:]:
        world.sunday(day, head_count=10).crowd(day, [30])
    world.crowd(sundays_of(2025, 1)[0], [30])
    assert run("cl.year-wrap", world.frames()) == []  # 29 regular Sundays: too few
    for sid in range(1, 13):
        world.special(sid, days[15])
    (fact,) = run("cl.year-wrap", world.frames())
    assert (fact.params["sundays"], fact.params["rounds"]) == (30, 29)
    assert (fact.params["busiest"], fact.params["busiest_n"]) == (days[15], 12)
    assert fact.params["firsts"] == 29 + 12
```

- [ ] **Step 4: Write the failing world tests**

Create `backend/tests/integration/special/test_special_trophies_insights.py`:

```python
"""Trophies and insights in the special world (Plan 17 Task 4, Review Focus 1 and 3)."""

from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.achievements.context import build_context
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.cohorts import cohort_returns
from sunday_clays.analytics.insights.attendance import held_run
from sunday_clays.analytics.insights.club import head_counts, special_turnout
from sunday_clays.analytics.insights.store import load_rows
from sunday_clays.analytics.steps.s60_insights import build_frames

SPECIAL, AFTER = date(2026, 9, 20), date(2026, 9, 27)
APPEARANCE_TROPHIES = {
    "events",
    "years_active",
    "big_year",
    "iron_streak",
    "new_year",
    "welcome_back",
    "four_seasons",
    "perfect_month",
    "anniversary_1",
    "anniversary_5",
}
APPEARANCE_INSIGHTS = {
    "pf.attendance-streak",
    "rec.streak-chase",
    "pf.sunday-milestone",
    "pf.shooter-anniversary",
    "pf.next-trophy",
    "pf.trophy-rare",
    "cl.turnout-trend",
    "cl.year-wrap",
    "cl.newcomers",
}


def _awards(session: Session) -> set[tuple[int, str, date]]:
    rows = session.execute(text("SELECT shooter_id, code, event_date FROM achievements_awarded"))
    return {(int(s), str(c), d) for s, c, d in rows}


def _family(code: str) -> str:
    return code.split(":", 1)[0]


def _shooter(session: Session, name: str) -> int:
    return int(
        session.execute(
            text("SELECT shooter_id FROM shooter_profiles WHERE display_name = :n"), {"n": name}
        ).scalar_one()
    )


def test_score_trophies_are_unchanged_by_the_special_sunday(
    fx_session: Session, fx_special_session: Session
) -> None:
    changed = _awards(fx_session) ^ _awards(fx_special_session)

    assert changed, "the special Sunday must move some appearance trophy"
    assert {_family(code) for _, code, _ in changed} <= APPEARANCE_TROPHIES


def test_a_shooter_new_at_the_special_sunday_earns_events_attended_and_nothing_scored(
    fx_special_session: Session,
) -> None:
    kim = _shooter(fx_special_session, "Kim, Pat")
    rows = fx_special_session.execute(
        text("SELECT code, event_date, round_id FROM achievements_awarded WHERE shooter_id = :s"),
        {"s": kim},
    ).all()

    assert ("events", SPECIAL) in {(_family(c), d) for c, d, _ in rows}
    assert {_family(c) for c, _, _ in rows} <= APPEARANCE_TROPHIES
    assert all(rid is None for _, _, rid in rows)


def test_the_trophy_context_sees_the_special_sunday_as_an_appearance(
    fx_special_session: Session,
) -> None:
    clear_cache()
    ctx = build_context(fx_special_session)
    hadley = _shooter(fx_special_session, "Hadley, Ike")

    days = ctx.attendance_days[ctx.attendance_days["shooter_id"] == hadley]
    special = days[days["event_date"] == SPECIAL].iloc[0]
    assert bool(special["special"]) is True
    assert pd.isna(special["best_round_id"])
    assert SPECIAL not in set(ctx.shooter_days["event_date"])


def test_insight_runs_and_counts_include_the_special_sunday(
    fx_session: Session, fx_special_session: Session
) -> None:
    clear_cache()
    base = build_frames(fx_session)
    clear_cache()
    special = build_frames(fx_special_session)
    hadley = _shooter(fx_special_session, "Hadley, Ike")

    base_days = base.history_until(hadley, AFTER)
    special_days = special.history_until(hadley, AFTER)
    assert held_run(special, special_days)[0] == held_run(base, base_days)[0] + 1
    assert special.appearances_through(hadley, AFTER) == base.appearances_through(hadley, AFTER) + 1
    assert special_days[-1].k == base_days[-1].k + 1
    # insights never anchor on a special Sunday (round ids differ between the worlds)
    assert [s.date for s in special.sundays] == [s.date for s in base.sundays]


def test_only_appearance_insights_change(fx_session: Session, fx_special_session: Session) -> None:
    def rows(session: Session) -> set[tuple[Any, ...]]:
        return {(r.key, r.value_hash, r.kind) for r in load_rows(session)}

    changed = rows(fx_session) ^ rows(fx_special_session)

    assert {kind for _, _, kind in changed} <= APPEARANCE_INSIGHTS
    assert all(r.anchor_date != SPECIAL for r in load_rows(fx_special_session))


def test_club_turnout_and_newcomers_count_the_special_sunday(
    fx_session: Session, fx_special_session: Session
) -> None:
    clear_cache()
    base = build_frames(fx_session)
    clear_cache()
    special = build_frames(fx_special_session)
    start = base.sundays[0].date

    assert special_turnout(base, start, AFTER) == []
    # the weekly workbook has no head count for 2026-09-20, so its turnout is its 5 shooters
    assert special_turnout(special, start, AFTER) == [(SPECIAL, 5.0)]
    assert head_counts(special, start, AFTER) == sorted(
        [*head_counts(base, start, AFTER), (SPECIAL, 5.0)]
    )

    def new_in_2026(fr: Any) -> int:
        returns = cohort_returns(fr.appearances, fr.shooters)
        return int(returns.loc[returns["cohort_year"] == 2026, "n_cohort"].iloc[0])

    assert new_in_2026(special) == new_in_2026(base) + 1  # Kim, Pat
```

- [ ] **Step 5: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/unit/analytics/achievements/test_ach_participation.py tests/unit/analytics/insights/test_kinds_attendance.py tests/unit/analytics/insights/test_kinds_milestones.py tests/unit/analytics/insights/test_kinds_records.py tests/integration/special/test_special_trophies_insights.py`
Expected: FAIL. `AchContext.from_frames()` and `InsightFrames.from_frames()` reject `appearances`/`calendar` (TypeError), so every new unit test errors (the club and community ones included, since `World.frames()` passes them); the world tests fail because the trophy and insight steps still see only regular Sundays (no award moves, `attendance_days` does not exist), and `special_turnout` cannot be imported.

- [ ] **Step 6: Write the trophy context and the attendance trophies**

In `backend/src/sunday_clays/analytics/achievements/context.py`:

1. After `_VALUE_DTYPES = {...}`, add:

```python
_ATTENDANCE_DTYPES: dict[str, str] = {
    "shooter_id": "int64",
    "event_ts": _TS_DTYPE,
    "event_date": "object",
    "special": "bool",
    "n_events": "int64",
    "prev_ts": _TS_DTYPE,
    "best_round_id": "Int64",
}
```

2. After `_shooter_days`, add:

```python
def _attendance_days(appearances: pd.DataFrame, shooter_days: pd.DataFrame) -> pd.DataFrame:
    """One row per shooter per Sunday shot, special Sundays included (Plan 17): the view the
    attendance trophies read. best_round_id is the day's best round, <NA> on a special Sunday."""
    if appearances.empty:
        return _empty(_ATTENDANCE_DTYPES)
    days = (
        appearances[["shooter_id", "event_ts", "kind"]]
        .drop_duplicates(["shooter_id", "event_ts"])
        .sort_values(["shooter_id", "event_ts"], kind="stable")
        .reset_index(drop=True)
    )
    days["shooter_id"] = days["shooter_id"].astype("int64")
    days["event_date"] = days["event_ts"].dt.date
    days["special"] = days["kind"].eq(frames.EVENT_KIND_SPECIAL)
    by_shooter = days.groupby("shooter_id", sort=False)
    days["n_events"] = by_shooter.cumcount() + 1
    days["prev_ts"] = by_shooter["event_ts"].shift(1)
    best = shooter_days[["shooter_id", "event_ts", "best_round_id"]]
    days = days.merge(best, on=["shooter_id", "event_ts"], how="left")
    days["best_round_id"] = days["best_round_id"].astype("Int64")
    return days[list(_ATTENDANCE_DTYPES)]
```

3. Replace the class from `@dataclass(frozen=True, eq=False)` down to the end of `streaks_at` with:

```python
@dataclass(frozen=True, eq=False)
class AchContext:
    """Frames as frames.load_* return them, each with an extra `event_ts` (datetime64) column.

    `rounds`, `events` and `station_hits` are regular Sundays only (score trophies read them);
    `appearances` and `calendar` include special Sundays (attendance trophies, Plan 17).
    """

    rounds: pd.DataFrame
    events: pd.DataFrame
    station_hits: pd.DataFrame
    rating_history: pd.DataFrame
    appearances: pd.DataFrame
    calendar: pd.DataFrame
    as_of: date | None = None
    _memo: dict[Any, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_frames(
        cls,
        *,
        rounds: pd.DataFrame,
        events: pd.DataFrame,
        station_hits: pd.DataFrame,
        rating_history: pd.DataFrame,
        appearances: pd.DataFrame | None = None,
        calendar: pd.DataFrame | None = None,
        as_of: date | None = None,
    ) -> AchContext:
        """Without appearances/calendar, the rounds and events imply them (all regular)."""
        return cls(
            rounds=_with_ts(rounds),
            events=_with_ts(events),
            station_hits=_with_ts(station_hits),
            rating_history=_with_ts(rating_history),
            appearances=_with_ts(
                frames.appearances_from_rounds(rounds) if appearances is None else appearances
            ),
            calendar=_with_ts(frames.calendar_from_events(events) if calendar is None else calendar),
            as_of=as_of,
        )

    def until(self, as_of: date | None) -> AchContext:
        """Only data dated <= as_of (None → this context unchanged)."""
        if as_of is None:
            return self
        return AchContext(
            rounds=_cut(self.rounds, as_of),
            events=_cut(self.events, as_of),
            station_hits=_cut(self.station_hits, as_of),
            rating_history=_cut(self.rating_history, as_of),
            appearances=_cut(self.appearances, as_of),
            calendar=_cut(self.calendar, as_of),
            as_of=as_of,
        )

    def for_shooter(self, shooter_id: int) -> AchContext:
        """One shooter's rows; events and the calendar stay whole (held Sundays are club-wide)."""
        linked = self.station_hits["shooter_id"].eq(shooter_id).fillna(False).astype(bool)
        return AchContext(
            rounds=self.rounds[self.rounds["shooter_id"] == shooter_id],
            events=self.events,
            station_hits=self.station_hits[linked],
            rating_history=self.rating_history[self.rating_history["shooter_id"] == shooter_id],
            appearances=self.appearances[self.appearances["shooter_id"] == shooter_id],
            calendar=self.calendar,
            as_of=self.as_of,
        )

    @property
    def shooter_days(self) -> pd.DataFrame:
        cached: pd.DataFrame | None = self._memo.get("shooter_days")
        if cached is None:
            cached = _shooter_days(self.rounds)
            self._memo["shooter_days"] = cached
        return cached

    @property
    def attendance_days(self) -> pd.DataFrame:
        """Every Sunday shot, special ones included (Plan 17); see _attendance_days."""
        cached: pd.DataFrame | None = self._memo.get("attendance_days")
        if cached is None:
            cached = _attendance_days(self.appearances, self.shooter_days)
            self._memo["attendance_days"] = cached
        return cached

    def held_dates(self) -> list[date]:
        """Regular held Sundays."""
        return sorted(held_event_dates(self.events, self.as_of))

    def calendar_held_dates(self) -> list[date]:
        """Every held Sunday, special ones included."""
        return sorted(held_event_dates(self.calendar, self.as_of))

    def streaks_at(self, day: date) -> pd.DataFrame:
        """C7 streaks over appearances: a special Sunday extends a run, never breaks one."""
        key = ("streaks", day)
        if key not in self._memo:
            self._memo[key] = streaks(self.appearances, self.calendar, day)
        result: pd.DataFrame = self._memo[key]
        return result
```

4. In `build_context`, replace

```python
        rounds=inspect.unwrap(frames.load_rounds)(session),
        events=inspect.unwrap(frames.load_events)(session),
        station_hits=load_station_entries(session),
        rating_history=inspect.unwrap(frames.load_rating_history)(session),
    )
```

with

```python
        rounds=inspect.unwrap(frames.load_rounds)(session),
        events=inspect.unwrap(frames.load_events)(session),
        station_hits=load_station_entries(session),
        rating_history=inspect.unwrap(frames.load_rating_history)(session),
        appearances=inspect.unwrap(frames.load_appearances)(session),
        calendar=inspect.unwrap(frames.load_calendar)(session),
    )
```

In `backend/src/sunday_clays/analytics/achievements/participation.py`:

1. Add `from typing import cast` to the imports and, after `_series`, the helper:

```python
def _round_id(value: object) -> int | None:
    """A day's best round id, or None on a special Sunday (no scored round, Plan 17)."""
    return None if pd.isna(value) else int(cast(int, value))
```

2. In `events_value`, `years_active_value`, `big_year_value` and `iron_streak_value`, replace `days = ctx.shooter_days` with `days = ctx.attendance_days` (four replacements; `clays_broken_value`, `clays_thrown_value` and `personal_bests_value` keep `ctx.shooter_days`).

3. Replace `_new_year` with:

```python
def _new_year(ctx: AchContext) -> Iterator[Award]:
    """The year's first regular held Sunday, and any special Sunday before it (Decision 10).

    Each shooter at most once a year, at the earliest of those Sundays they shot."""
    regular = ctx.held_dates()
    first_regular: dict[int, date] = {}
    for day in regular:
        first_regular.setdefault(day.year, day)
    qualifying = set(first_regular.values()) | {
        day
        for day in ctx.calendar_held_dates()
        if day not in set(regular)
        and (day.year not in first_regular or day < first_regular[day.year])
    }
    days = ctx.attendance_days
    hits = days[days["event_date"].isin(qualifying)]
    hits = hits.assign(year=hits["event_ts"].dt.year).drop_duplicates(["shooter_id", "year"])
    for sid, day, rid in zip(
        hits["shooter_id"], hits["event_date"], hits["best_round_id"], strict=True
    ):
        yield Award(int(sid), "new_year", day, _round_id(rid), {"year": day.year})
```

4. In `_anniversary`'s `evaluate` and in `_four_seasons`, replace `days = ctx.shooter_days` with `days = ctx.attendance_days`.

5. Replace `_welcome_back` with:

```python
def _welcome_back(ctx: AchContext) -> Iterator[Award]:
    days = ctx.attendance_days
    gap = (days["event_ts"] - days["prev_ts"]).dt.days
    back = gap >= WELCOME_BACK_DAYS
    hits = days[back]
    for sid, day, rid, away in zip(
        hits["shooter_id"], hits["event_date"], hits["best_round_id"], gap[back], strict=True
    ):
        yield Award(int(sid), "welcome_back", day, _round_id(rid), {"days_away": int(away)})
```

6. Replace `_perfect_month` with:

```python
def _perfect_month(ctx: AchContext) -> Iterator[Award]:
    """Month M with >= 3 Sundays, every regular held one attended.

    Dated at the closing event: the first held event on or after M's last calendar Sunday L
    (L itself when L was held). Only M's held events up to the closing event count, so a held
    non-Sunday after a held L cannot change an award already dated L (no leak, never moves).
    A special Sunday shot in M up to the closing event counts toward the three and is never
    required (Plan 17, Decision 10)."""
    held = ctx.held_dates()
    days = ctx.attendance_days
    attendees: dict[date, set[int]] = {}
    specials: dict[int, list[date]] = {}
    for sid, day, special in zip(
        days["shooter_id"], days["event_date"], days["special"], strict=True
    ):
        if special:
            specials.setdefault(int(sid), []).append(day)
        else:
            attendees.setdefault(day, set()).add(int(sid))
    months: dict[tuple[int, int], list[date]] = {}
    for day in held:
        months.setdefault((day.year, day.month), []).append(day)
    for (year, month), month_days in sorted(months.items()):
        cutoff = last_sunday(year, month)
        closing = next((day for day in held if day >= cutoff), None)
        if closing is None:
            continue
        counted = [day for day in month_days if day <= closing]
        perfect = set(attendees.get(counted[0], set()))
        for day in counted[1:]:
            perfect &= attendees.get(day, set())
        for sid in sorted(perfect):
            extra = sum(
                1
                for day in specials.get(sid, ())
                if (day.year, day.month) == (year, month) and day <= closing
            )
            if len(counted) + extra < PERFECT_MONTH_MIN_EVENTS:
                continue
            yield Award(sid, "perfect_month", closing, None, {"month": f"{year:04d}-{month:02d}"})
```

- [ ] **Step 7: Write the appearance-aware insights**

In `backend/src/sunday_clays/analytics/insights/context.py`:

1. Replace `from bisect import bisect_right` with `from bisect import bisect_left, bisect_right`.

2. Replace the class header and `from_frames`/`until` (from `@dataclass(frozen=True)\nclass InsightFrames:` through the end of `until`) with:

```python
@dataclass(frozen=True)
class InsightFrames:
    rounds: pd.DataFrame  # C7 load_rounds columns (event_date as datetime.date)
    events: pd.DataFrame  # C7 load_events columns
    shooters: pd.DataFrame  # frames.SHOOTER_COLUMNS
    rating: pd.DataFrame  # frames.RATING_COLUMNS
    stations: pd.DataFrame  # frames.STATION_HIT_COLUMNS
    awards: pd.DataFrame  # AWARD_COLUMNS
    appearances: pd.DataFrame  # frames.APPEARANCE_COLUMNS: special Sundays included (Plan 17)
    calendar: pd.DataFrame  # frames.CALENDAR_COLUMNS: special Sundays included (Plan 17)
    as_of: date | None  # latest held (regular) Sunday in these frames
    histories: Mapping[int, tuple[Day, ...]] = field(repr=False)
    sundays: tuple[Sunday, ...] = field(repr=False)
    sunday_index: Mapping[date, int] = field(repr=False)
    profiles: Mapping[int, Profile] = field(repr=False)
    ratings: Mapping[int, tuple[tuple[date, float], ...]] = field(repr=False)
    appearance_dates: Mapping[int, tuple[date, ...]] = field(repr=False)
    special_days: Mapping[int, tuple[date, ...]] = field(repr=False)

    @classmethod
    def from_frames(
        cls,
        *,
        rounds: pd.DataFrame,
        events: pd.DataFrame,
        shooters: pd.DataFrame,
        rating: pd.DataFrame,
        stations: pd.DataFrame | None = None,
        awards: pd.DataFrame | None = None,
        appearances: pd.DataFrame | None = None,
        calendar: pd.DataFrame | None = None,
    ) -> InsightFrames:
        """Without appearances/calendar, the rounds and events imply them (all regular)."""
        stations = (
            stations if stations is not None else pd.DataFrame(columns=list(fr.STATION_HIT_COLUMNS))
        )
        awards = awards if awards is not None else pd.DataFrame(columns=list(AWARD_COLUMNS))
        appearances = fr.appearances_from_rounds(rounds) if appearances is None else appearances
        calendar = fr.calendar_from_events(events) if calendar is None else calendar
        dates = _dates_by_shooter(appearances)
        sundays = _build_sundays(rounds, events)
        return cls(
            rounds=rounds,
            events=events,
            shooters=shooters,
            rating=rating,
            stations=stations,
            awards=awards,
            appearances=appearances,
            calendar=calendar,
            as_of=sundays[-1].date if sundays else None,
            histories=_build_histories(rounds, events, dates),
            sundays=sundays,
            sunday_index={s.date: s.i for s in sundays},
            profiles=_build_profiles(shooters),
            ratings=_build_ratings(rating),
            appearance_dates=dates,
            special_days=_dates_by_shooter(appearances, special_only=True),
        )

    def until(self, day: date) -> InsightFrames:
        """Everything as it was known on `day`: every frame cut at `event_date <= day`."""

        def cut(df: pd.DataFrame) -> pd.DataFrame:
            return df.loc[[d <= day for d in df["event_date"]]] if len(df) else df

        return InsightFrames.from_frames(
            rounds=cut(self.rounds),
            events=cut(self.events),
            shooters=self.shooters,
            rating=cut(self.rating),
            stations=cut(self.stations),
            awards=cut(self.awards),
            appearances=cut(self.appearances),
            calendar=cut(self.calendar),
        )

    def appearances_through(self, shooter_id: int, day: date) -> int:
        """Sundays the shooter shot up to `day`, special ones included (Plan 17)."""
        return bisect_right(self.appearance_dates.get(shooter_id, ()), day)

    def specials_through(self, shooter_id: int, day: date) -> tuple[date, ...]:
        """The special Sundays the shooter shot up to `day`, oldest first."""
        days = self.special_days.get(shooter_id, ())
        return days[: bisect_right(days, day)]

    @cached_property
    def _held_sorted(self) -> list[date]:
        return self.held_dates()

    def no_held_between(self, earlier: date, later: date) -> bool:
        """No regular held Sunday strictly between the two dates (C7 streaks, Plan 17)."""
        held = self._held_sorted
        return bisect_left(held, later) == bisect_right(held, earlier)
```

3. Add, before `_build_sundays`:

```python
def _dates_by_shooter(
    appearances: pd.DataFrame, *, special_only: bool = False
) -> dict[int, tuple[date, ...]]:
    frame = (
        appearances.loc[appearances["kind"].eq(fr.EVENT_KIND_SPECIAL)]
        if special_only
        else appearances
    )
    out: dict[int, set[date]] = defaultdict(set)
    for sid, day in zip(frame["shooter_id"], frame["event_date"], strict=True):
        out[int(sid)].add(day)
    return {sid: tuple(sorted(days)) for sid, days in out.items()}
```

4. In `_build_histories`, replace the signature

```python
def _build_histories(rounds: pd.DataFrame, events: pd.DataFrame) -> dict[int, tuple[Day, ...]]:
```

with

```python
def _build_histories(
    rounds: pd.DataFrame,
    events: pd.DataFrame,
    appearance_dates: Mapping[int, tuple[date, ...]] | None = None,
) -> dict[int, tuple[Day, ...]]:
    dates = appearance_dates or {}
```

and replace

```python
                k=len(days) + 1,
```

with

```python
                # Sundays shot through this date, special ones included (Plan 17)
                k=bisect_right(dates[sid], day) if sid in dates else len(days) + 1,
```

and change the `Day.k` field comment to `# Sundays shot through this date, special ones included (Plan 17)`.

In `backend/src/sunday_clays/analytics/insights/attendance.py`, replace `held_run` and `longest_before` with:

```python
def _attended(fr: InsightFrames, days: Sequence[Day]) -> list[date]:
    """Dates that count toward a run of Sundays in a row: the held Sundays shot, plus the special
    Sundays shot up to the last day (C7 streaks: a special Sunday extends a run, never breaks one)."""
    regular = [d.date for d in held_only(days)]
    special = fr.specials_through(days[-1].shooter_id, days[-1].date)
    return sorted({*regular, *special})


def held_run(fr: InsightFrames, days: Sequence[Day]) -> tuple[int, date | None]:
    """(Sundays in a row ending at the last day, the run's first Sunday); C7 `streaks`."""
    if not days or not days[-1].held:
        return 0, None
    dates = _attended(fr, days)
    i = len(dates) - 1
    while i > 0 and fr.no_held_between(dates[i - 1], dates[i]):
        i -= 1
    return len(dates) - i, dates[i]


def longest_before(fr: InsightFrames, days: Sequence[Day]) -> int:
    if not days:
        return 0
    dates = _attended(fr, days)
    longest = run = 0
    for j, day in enumerate(dates):
        run = run + 1 if j and fr.no_held_between(dates[j - 1], day) else 1
        longest = max(longest, run)
    return longest
```

In `backend/src/sunday_clays/analytics/insights/milestones.py` (`_sunday_milestone`), replace

```python
    for sid, days in evergreen_days(fr, scope):
        last = days[-1]
        nxt = next((level for level in SUNDAY_LEVELS if level > last.k), None)
        if nxt is None or nxt - last.k > TO_GO_MAX or not shot_recently(days, scope.as_of):
            continue
```

with

```python
    for sid, days in evergreen_days(fr, scope):
        last = days[-1]
        shot = fr.appearances_through(sid, scope.as_of)  # special Sundays count (Decision 11)
        nxt = next((level for level in SUNDAY_LEVELS if level > shot), None)
        if nxt is None or nxt - shot > TO_GO_MAX or not shot_recently(days, scope.as_of):
            continue
```

and replace `                "to_go": nxt - last.k,` with `                "to_go": nxt - shot,`.

In `backend/src/sunday_clays/analytics/insights/records.py` (`_streak_chase`), replace

```python
    table = streaks(fr.rounds, fr.events, scope.as_of)
```

with

```python
    table = streaks(fr.appearances, fr.calendar, scope.as_of)  # special Sundays extend runs
```

In `backend/src/sunday_clays/analytics/insights/anchors.py` (`streak_rows`), replace

```python
    table = streaks(fr.rounds, fr.events, link.window.end)
```

with

```python
    table = streaks(fr.appearances, fr.calendar, link.window.end)
```

In `backend/src/sunday_clays/analytics/insights/trophies.py` (`_next_trophy`), replace

```python
        station_hits=fr.stations[list(STATION_COLUMNS)],
        rating_history=fr.rating,
    )
```

with

```python
        station_hits=fr.stations[list(STATION_COLUMNS)],
        rating_history=fr.rating,
        appearances=fr.appearances,
        calendar=fr.calendar,
    )
```

In `backend/src/sunday_clays/analytics/steps/s60_insights.py` (`build_frames`), replace

```python
        stations=inspect.unwrap(frames.load_station_hits)(session),
        awards=awards,
    )
```

with

```python
        stations=inspect.unwrap(frames.load_station_hits)(session),
        awards=awards,
        appearances=inspect.unwrap(frames.load_appearances)(session),
        calendar=inspect.unwrap(frames.load_calendar)(session),
    )
```

In `backend/src/sunday_clays/analytics/insights/club.py` (`frames` and `pd` are already imported), replace `head_counts` with:

```python
def special_turnout(fr: InsightFrames, start: date, end: date) -> list[tuple[date, float]]:
    """(date, turnout) of every held special Sunday in [start, end], oldest first (Plan 17): its
    head count, else the shooters on its sheet (the insights' `head_count or n` turnout rule)."""
    cal = fr.calendar
    return sorted(
        (day, float(n if pd.isna(heads) else heads))
        for day, kind, heads, n, held in zip(
            cal["event_date"],
            cal["kind"],
            cal["head_count"],
            cal["n_shooters"],
            cal["results_complete"],
            strict=True,
        )
        if kind == frames.EVENT_KIND_SPECIAL and bool(held) and start <= day <= end
    )


def head_counts(fr: InsightFrames, start: date, end: date) -> list[tuple[date, float]]:
    """(date, head count) of every event in [start, end] with one, oldest first: the Explorer
    `attendance` rows (Plan 11 T2 turnout rule; an event without full results still counts),
    plus every held special Sunday's turnout (Plan 17: club turnout counts special Sundays)."""
    regular = [
        (day, float(heads))
        for day, heads in zip(fr.events["event_date"], fr.events["head_count"], strict=True)
        if start <= day <= end and not pd.isna(heads)
    ]
    return sorted([*regular, *special_turnout(fr, start, end)])
```

`turnout_by_band` (`cl.rain-turnout`) keeps reading `fr.events` (Decision 8).

In `backend/src/sunday_clays/analytics/insights/community.py`:

1. Replace `from sunday_clays.analytics.insights.club import CLUB, held_to` with `from sunday_clays.analytics.insights.club import CLUB, held_to, special_turnout`, and add after `_rounds_to`:

```python
def _appearances_to(fr: InsightFrames, day: date) -> pd.DataFrame:
    return fr.appearances.loc[[d <= day for d in fr.appearances["event_date"]]]
```

2. In `_newcomers`, replace `    returns = cohort_returns(_rounds_to(fr, scope.as_of), fr.shooters)` with

```python
    # cohorts follow Sundays shot, like the /club "new" chart this links to (Plan 17)
    returns = cohort_returns(_appearances_to(fr, scope.as_of), fr.shooters)
```

3. Replace `_year_wrap` with:

```python
def _year_wrap(fr: InsightFrames, scope: Scope) -> Iterator[Fact]:
    wrapping = wrap_year(scope.as_of)  # December/January: the year just wrapping, on home too
    year = scope.as_of.year - 1 if wrapping is None else wrapping
    held = held_to(fr, scope.as_of)
    sundays = [s for s in held if s.date.year == year]
    # special Sundays are Sundays held, can be the busiest, and bring first-timers (Plan 17);
    # the round count stays the scored rounds
    specials = special_turnout(fr, date(year, 1, 1), min(date(year, 12, 31), scope.as_of))
    if not held or len(sundays) + len(specials) < CLUB_WRAP_MIN:
        return
    rounds = _rounds_to(fr, scope.as_of)
    in_year = rounds.loc[[d.year == year for d in rounds["event_date"]]]
    firsts = sum(
        1
        for sid, dates in fr.appearance_dates.items()
        if dates and dates[0].year == year and not fr.profiles[sid].left_censored
    )
    busiest_n, busiest = max(
        [(float(s.head_count or s.n), s.date) for s in sundays]
        + [(turnout, day) for day, turnout in specials]
    )
    params = {
        "first": held[0].date,
        "year": year,
        "sundays": len(sundays) + len(specials),
        "rounds": len(in_year),
        "firsts": firsts,
        "busiest": busiest,
        "busiest_n": round(busiest_n),
    }
    pages = {P.CLUB} | ({P.HOME} if wrapping is not None else set())
    yield _fact(scope, frozenset(pages), params, 1.0)
```

Without a special Sunday this is the old rule exactly: `appearance_dates` holds the same first dates as `histories`, and `(head_count or n, date)` picks the same busiest Sunday, so `test_kinds_community.py`'s existing cases and the insight goldens stay green. `ev.rain-day` in `insights/sunday.py` is not touched (Decision 8).

- [ ] **Step 8: Run them to verify they pass**

Run: `cd backend && uv run ruff format src tests && uv run pytest -q tests/unit/analytics/achievements tests/unit/analytics/insights tests/integration/special tests/integration/achievements tests/integration/insights`
Expected: all pass, including every achievement and insight golden (`test_ach_*_golden.py`, `test_golden_counts.py`, `test_no_leak.py`) unchanged, and `test_performance.py` inside its loose ceiling.

- [ ] **Step 9: Gates and the full backend suite with coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest -q --cov --cov-branch`
Expected: all green, coverage at or above 90% lines and branches.

- [ ] **Step 10: Commit**

```bash
git add backend/src/sunday_clays/analytics/achievements/context.py backend/src/sunday_clays/analytics/achievements/participation.py backend/src/sunday_clays/analytics/insights/context.py backend/src/sunday_clays/analytics/insights/attendance.py backend/src/sunday_clays/analytics/insights/milestones.py backend/src/sunday_clays/analytics/insights/records.py backend/src/sunday_clays/analytics/insights/anchors.py backend/src/sunday_clays/analytics/insights/trophies.py backend/src/sunday_clays/analytics/insights/club.py backend/src/sunday_clays/analytics/insights/community.py backend/src/sunday_clays/analytics/steps/s60_insights.py backend/tests/unit/analytics/achievements/conftest.py backend/tests/unit/analytics/achievements/test_ach_participation.py backend/tests/unit/analytics/insights/conftest.py backend/tests/unit/analytics/insights/test_kinds_attendance.py backend/tests/unit/analytics/insights/test_kinds_milestones.py backend/tests/unit/analytics/insights/test_kinds_records.py backend/tests/unit/analytics/insights/test_kinds_club.py backend/tests/unit/analytics/insights/test_kinds_community.py backend/tests/integration/special/test_special_trophies_insights.py
git commit -m "feat(special): attendance trophies and insights count special Sundays (Plan 17 T4)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The API: Sunday payloads, the profile, boards, records, club and Year in Review

Every route that reads the score frames is already clean after Task 3. This task switches the appearance consumers of Decision 7 to the appearance frames, keeps the insight feeds' reference Sunday on regular Sundays (`api/routes/insights.py held_dates` reads `events` directly, so it is a seam of its own), adds the special Sunday's display data and the `/special` list, and proves both halves route by route.

**Files:**
- Modify: `backend/src/sunday_clays/api/routes/events.py`, `api/routes/shooters.py`, `api/routes/shooter_insights.py`, `api/routes/club.py`, `api/routes/club_insights.py`, `api/routes/insights.py`
- Modify: `backend/src/sunday_clays/analytics/leaderboards.py`, `analytics/records.py`, `analytics/yir.py`, `analytics/club_insights.py`, `analytics/profile.py`
- Modify: `backend/tests/unit/analytics/competition/test_leaderboard_metrics.py`, `tests/unit/analytics/records/test_records_unit.py`, `tests/unit/extras/test_extras_yir.py`, `tests/unit/analytics_core/test_club_insights.py`, `tests/unit/analytics_core/test_shooter_profile.py`
- Create: `backend/tests/integration/special/test_special_routes.py`

**Interfaces:**
- Consumes: Task 3's frames (`load_calendar`, `load_appearances`, `load_special_rounds`, `load_special_station_hits`, `appearances_from_rounds`, `calendar_from_events`, `EVENT_KIND_*`, `REGULAR_TARGETS`) and the streak rule; `fx_viewer_client`, `fx_special_viewer_client`.
- Produces (Tasks 6, 7 and 8 rely on these through `pnpm gen:api`):
  - `EventSummaryOut`, `EventDetailOut`, `AttendanceOut`: `kind: "regular" | "special" = "regular"`, `label: str | None = None`, `target_total: int = 50`.
  - A special Sunday's `EventDetailOut`: `results` best first with every metric `null`, `is_best_round: true`, `event_rank: null`; `stations` its grid; `vs_prev: null`; `notables` first-timers only.
  - `GET /api/shooters/{id}/special` → `list[SpecialRoundOut{round_id, event_date, label, target_total, score}]`, oldest first; 404 `shooter_not_found`.
  - `make_leaderboard_frames(rounds, events, history, appearances=None)`; `LeaderboardFrames.appearances`.
  - `compute_records(..., appearances=None, calendar=None)`; `yearly_trends(rounds, events, as_of, appearances=None)`; `shooter_insights(..., appearances=None)`; `YirFrames.appearances: DataFrame | None = None`; `odometer(rounds, streak_row, trophies, sundays=None)`.

- [ ] **Step 1: Write the failing unit tests**

Append to `backend/tests/unit/analytics/competition/test_leaderboard_metrics.py`:

```python
def test_the_sundays_board_counts_special_sundays_and_score_boards_do_not(
    fb: FrameBuilder,
) -> None:
    from sunday_clays.analytics import frames
    from sunday_clays.analytics.leaderboards import make_leaderboard_frames

    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    fb.day(D1, {1: 40}).day(D3, {1: 41})
    rounds = fb.rounds()
    special = pd.DataFrame(
        [
            {
                "shooter_id": sid,
                "event_date": D2,
                "kind": "special",
                "round_type": "sporting",
                "display_name": name,
                "shooter_status": "member",
                "name_key": key,
                "held": True,
            }
            for sid, name, key in [(1, "Ace, Amy", "ace amy"), (2, "Bee, Bob", "bee bob")]
        ],
        columns=list(frames.APPEARANCE_COLUMNS),
    )
    seen = pd.concat([frames.appearances_from_rounds(rounds), special], ignore_index=True)
    lf = make_leaderboard_frames(rounds, fb.events(), fb.history(), seen)

    sundays = leaderboard(lf, ALL, LeaderboardMetric.EVENTS, D3)
    assert values(sundays) == {1: 3.0, 2: 1.0}
    assert [r.display_name for r in sundays.records()] == ["Ace, Amy", "Bee, Bob"]
    assert values(leaderboard(lf, ALL, LeaderboardMetric.BEST_SCORE, D3)) == {1: 41.0}
    assert values(leaderboard(lf, ALL, LeaderboardMetric.ROUNDS, D3)) == {1: 2.0}
    gauged = leaderboard(
        lf, ALL, LeaderboardMetric.EVENTS, D3, LeaderboardFilters(gauge="unspecified")
    )
    assert values(gauged) == {1: 2.0}  # a gauge filter counts scored Sundays (Decision 7)


def test_a_special_sheet_spelling_never_reorders_tied_score_rows(fb: FrameBuilder) -> None:
    """The D6 tie key comes from scored rounds (Plan 17): a special-sheet spelling that sorts
    before the shooter's own key (an alias-ruled first name) must not move tied rows."""
    from sunday_clays.analytics import frames
    from sunday_clays.analytics.leaderboards import make_leaderboard_frames

    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    fb.day(D1, {1: 40, 2: 40})
    rounds = fb.rounds()
    special = pd.DataFrame(
        [
            {
                "shooter_id": sid,
                "event_date": D2,
                "kind": "special",
                "round_type": "sporting",
                "display_name": name,
                "shooter_status": "member",
                "name_key": key,
                "held": True,
            }
            # 2's sheet spelling sorts before "ace amy"; 3 shot only the special Sunday
            for sid, name, key in [(2, "Bee, Bob", "aardvark bob"), (3, "Cy, Cal", "cy cal")]
        ],
        columns=list(frames.APPEARANCE_COLUMNS),
    )
    seen = pd.concat([frames.appearances_from_rounds(rounds), special], ignore_index=True)
    plain = make_leaderboard_frames(rounds, fb.events(), fb.history())
    with_special = make_leaderboard_frames(rounds, fb.events(), fb.history(), seen)

    for lf in (plain, with_special):
        board = leaderboard(lf, ALL, LeaderboardMetric.BEST_SCORE, D3)
        assert [r.display_name for r in board.records()] == ["Ace, Amy", "Bee, Bob"]
    sundays = leaderboard(with_special, ALL, LeaderboardMetric.EVENTS, D3)
    assert [r.display_name for r in sundays.records()] == ["Bee, Bob", "Ace, Amy", "Cy, Cal"]
    keys = dict(zip(with_special.shooters["shooter_id"], with_special.shooters["sort_key"]))
    assert keys == {1: "ace amy", 2: "bee bob", 3: "cy cal"}
```

Append to `backend/tests/unit/analytics/records/test_records_unit.py`:

```python
def _seen(day: date, sid: int, kind: str) -> dict[str, Any]:
    return {
        "shooter_id": sid,
        "event_date": day,
        "kind": kind,
        "round_type": "sporting",
        "display_name": NAMES[sid],
        "shooter_status": "member",
        "name_key": NAMES[sid].casefold().replace(",", ""),
        "held": True,
    }


def test_most_sundays_and_longest_runs_count_special_sundays_but_scores_do_not() -> None:
    w = World().shot(D[0], 1, 40).shot(D[2], 1, 41).shot(D[0], 2, 30).shot(D[2], 2, 31)
    seen = pd.DataFrame(
        [
            _seen(D[0], 1, "regular"),
            _seen(D[0], 2, "regular"),
            _seen(D[1], 1, "special"),
            _seen(D[1], 3, "special"),
            _seen(D[2], 1, "regular"),
            _seen(D[2], 2, "regular"),
        ]
    )
    calendar = pd.DataFrame(
        [
            dict.fromkeys(EVENT_COLUMNS)
            | {
                "event_date": day,
                "round_type": "sporting",
                "has_scores": True,
                "results_complete": True,
                "kind": kind,
            }
            for day, kind in [(D[0], "regular"), (D[1], "special"), (D[2], "regular")]
        ]
    )
    base = w.records(as_of=D[2])

    records = w.records(as_of=D[2], appearances=seen, calendar=calendar)

    assert {(r.shooter_id, r.value) for r in records.most_events} == {(1, 3.0), (2, 2.0), (3, 1.0)}
    assert {(r.shooter_id, r.value) for r in records.longest_streaks} == {
        (1, 3.0),
        (2, 2.0),
        (3, 1.0),
    }
    assert records.highest_scores == base.highest_scores
    assert records.biggest_jumps == base.biggest_jumps
    assert records.perfect_rounds == base.perfect_rounds
```

Append to `backend/tests/unit/extras/test_extras_yir.py`:

```python
def test_special_sundays_count_as_sundays_but_never_as_rounds_in_the_year() -> None:
    special_day = date(2025, 2, 9)
    events = pd.concat(
        [
            WORLD.events.assign(kind="regular"),
            pd.DataFrame(
                [
                    {
                        "event_date": special_day,
                        "has_scores": True,
                        "results_complete": True,
                        "head_count": NAN,
                        "median": NAN,
                        "difficulty": NAN,
                        "round_type": "sporting",
                        "n_shooters": 2.0,
                        "top_score": NAN,
                        "kind": "special",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    regular = WORLD.rounds[["event_date", "shooter_id", "round_type"]].drop_duplicates()
    extra = pd.DataFrame(
        [(special_day, 1, "sporting"), (special_day, 4, "sporting")],
        columns=["event_date", "shooter_id", "round_type"],
    )
    data = replace(
        WORLD, events=events, appearances=pd.concat([regular, extra], ignore_index=True)
    )

    base, club = club_year(WORLD, 2025), club_year(data, 2025)
    assert club.totals.held_events == base.totals.held_events + 1
    assert club.totals.scored_events == base.totals.scored_events
    assert club.totals.shooters == base.totals.shooters + 1  # shooter 4's only 2025 Sunday
    assert (club.totals.rounds, club.totals.clays_thrown, club.totals.avg_score) == (
        base.totals.rounds,
        base.totals.clays_thrown,
        base.totals.avg_score,
    )
    assert club.events == base.events + 1
    assert club.months[1].events == base.months[1].events + 1
    assert club.months[1].rounds == base.months[1].rounds
    assert club.newcomers == base.newcomers
    mine, before = shooter_year(data, 1, 2025), shooter_year(WORLD, 1, 2025)
    assert mine.totals.events == before.totals.events + 1
    assert (mine.totals.rounds, mine.totals.clays_broken) == (
        before.totals.rounds,
        before.totals.clays_broken,
    )
    assert on_this_day(data, date(2026, 2, 9)) == on_this_day(WORLD, date(2026, 2, 9))
    assert scored_years(data) == scored_years(WORLD)
```

(Add `from dataclasses import replace` to that module's imports.)

Append to `backend/tests/unit/analytics_core/test_club_insights.py`:

```python
def test_yearly_trends_count_special_sundays_as_held_sundays_and_shooters(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    from sunday_clays.analytics import frames

    d1, d2, d3 = date(2026, 3, 1), date(2026, 3, 8), date(2026, 3, 15)
    rounds = make_rounds([(d1, 1, 30), (d3, 1, 31), (d1, 2, 30)])
    calendar = frames.calendar_from_events(make_events([d1, d2, d3]))
    calendar.loc[calendar["event_date"] == d2, "kind"] = "special"
    special = frames.appearances_from_rounds(make_rounds([(d2, 3, 40)])).assign(kind="special")
    seen = pd.concat([frames.appearances_from_rounds(rounds), special], ignore_index=True)

    (year,) = ci.yearly_trends(rounds, calendar, d3, seen)
    (base,) = ci.yearly_trends(rounds, make_events([d1, d3]), d3)

    assert (year.events_held, year.unique_shooters, year.ytd_unique_shooters) == (3, 3, 3)
    assert (base.events_held, base.unique_shooters, base.ytd_unique_shooters) == (2, 2, 2)
    assert year.ytd_rounds == base.ytd_rounds == 3
```

Append to `backend/tests/unit/analytics_core/test_shooter_profile.py`:

```python
def test_the_sundays_milestone_counts_special_sundays(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    from sunday_clays.analytics import frames

    days = [date(2026, 1, 4) + timedelta(weeks=i) for i in range(9)]
    special_day = days[-1] + timedelta(weeks=1)
    rounds = make_rounds([(d, 1, 30) for d in days])
    special = frames.appearances_from_rounds(make_rounds([(special_day, 1, 30)]))
    seen = pd.concat(
        [frames.appearances_from_rounds(rounds), special.assign(kind="special")],
        ignore_index=True,
    )
    shooters = pd.DataFrame(
        [(1, "Shooter 1", "member", days[0], special_day, 9, 10, False)],
        columns=list(frames.SHOOTER_COLUMNS),
    )
    history = pd.DataFrame(columns=list(frames.RATING_COLUMNS))

    base = profile.shooter_insights(rounds, history, shooters, 1, special_day)
    counted = profile.shooter_insights(rounds, history, shooters, 1, special_day, seen)

    assert (base.milestone.next_events, base.milestone.events_to_go) == (10, 1)
    assert (counted.milestone.next_events, counted.milestone.events_to_go) == (25, 15)
    assert counted.n_rounds == base.n_rounds == 9
```

- [ ] **Step 2: Write the failing route tests**

Create `backend/tests/integration/special/test_special_routes.py`:

```python
"""The API with a special Sunday (Plan 17 Task 5, Review Focus 1, 2 and 3).

Score routes answer exactly as in the regular world; appearance routes count the special Sunday.
"""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import clear_cache

SPECIAL, BEFORE, AFTER = "2026-09-20", "2026-09-13", "2026-09-27"
SCORE_LISTS = ("highest_scores", "perfect_rounds", "biggest_adjusted", "biggest_jumps",
               "highest_ratings")


def _get(client: TestClient, url: str) -> Any:
    response = client.get(url)
    assert response.status_code == 200, response.text
    return response.json()


def _both(base: TestClient, special: TestClient, url: str) -> tuple[Any, Any]:
    clear_cache()
    left = _get(base, url)
    clear_cache()
    return left, _get(special, url)


def _id(client: TestClient, name: str) -> int:
    (match,) = [s for s in _get(client, f"/api/shooters?q={name.split(',')[0]}")
                if s["display_name"] == name]
    return int(match["shooter_id"])


@pytest.mark.parametrize(
    "url",
    [
        "/api/leaderboards?period=all_time&metric=avg_score",
        f"/api/leaderboards?period=ytd&metric=best_score&as_of={AFTER}",
        "/api/leaderboards?period=all_time&metric=wins",
        "/api/leaderboards?period=all_time&metric=rounds",
        f"/api/leaderboards?period=rolling_12&metric=season_points&as_of={AFTER}",
        "/api/leaderboards?period=all_time&metric=events&gauge=unspecified",
        "/api/club/distribution",
        "/api/club/first-rounds",
        "/api/club/parity",
        "/api/club/conversion",
        f"/api/club/regulars?as_of={AFTER}",
        "/api/stations",
        "/api/weather/effects",
        f"/api/on-this-day?date={AFTER}",
    ],
)
def test_score_routes_answer_exactly_as_without_the_special_sunday(
    url: str, fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    base, special = _both(fx_viewer_client, fx_special_viewer_client, url)
    assert special == base


def test_a_shooters_score_views_are_unchanged(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    hadley = _id(fx_viewer_client, "Hadley, Ike")
    for tail in ("rounds", "rating", "splits?by=year", "stations"):
        base, special = _both(
            fx_viewer_client, fx_special_viewer_client, f"/api/shooters/{hadley}/{tail}"
        )
        assert special == base, tail
    query = {"metric": "score", "agg": "avg", "group_by": ["year"]}
    attendance = {"metric": "attendance", "agg": "avg", "group_by": ["year"]}
    for spec in (query, attendance):  # Explorer stays on scored Sundays (Decision 8)
        clear_cache()
        base_response = fx_viewer_client.post("/api/explore", json=spec)
        assert base_response.status_code == 200, base_response.text
        clear_cache()
        assert fx_special_viewer_client.post("/api/explore", json=spec).json() == base_response.json()


def test_insight_feeds_reference_regular_sundays_only(
    fx_viewer_client: TestClient,
    fx_special_viewer_client: TestClient,
    fx_session: Session,
    fx_special_session: Session,
) -> None:
    """The feeds' reference Sunday, home window and expiry count regular held Sundays only
    (Decision 12): the special Sunday never ages an insight or becomes the reference.

    The home feed cannot be compared whole: Decision 7's appearance and club-turnout kinds
    legitimately change in it. A shooter who skipped the special Sunday has no such kind, so that
    profile feed must match exactly; if it does not, find the kind that moved before touching
    this test."""
    from sunday_clays.api.routes.insights import held_dates

    held = held_dates(fx_special_session)
    assert held == held_dates(fx_session)
    assert date.fromisoformat(SPECIAL) not in held

    base, special = _both(fx_viewer_client, fx_special_viewer_client, "/api/insights/home")
    assert special["as_of"] == base["as_of"] != SPECIAL

    at_special = {
        r["shooter_id"] for r in _get(fx_special_viewer_client, f"/api/events/{SPECIAL}")["results"]
    }
    skipped = min(
        r["shooter_id"]
        for r in _get(fx_viewer_client, f"/api/events/{AFTER}")["results"]
        if r["shooter_id"] not in at_special
    )
    url = f"/api/insights/shooters/{skipped}?all=true"
    base, special = _both(fx_viewer_client, fx_special_viewer_client, url)
    base.pop("data_version")
    special.pop("data_version")
    assert special == base

    feed = _get(fx_special_viewer_client, f"/api/insights/sundays/{SPECIAL}")
    assert (feed["hero"], feed["top"], feed["kudos"], feed["more"]) == (None, [], [], [])


def test_records_keep_score_lists_and_count_the_special_sunday_in_sundays_and_runs(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    base, special = _both(
        fx_viewer_client, fx_special_viewer_client, f"/api/records?as_of={AFTER}&limit=all"
    )
    for name in SCORE_LISTS:
        assert special[name] == base[name], name
    hadley = _id(fx_viewer_client, "Hadley, Ike")
    kim = _id(fx_special_viewer_client, "Kim, Pat")

    def value(body: dict[str, Any], name: str, sid: int) -> float | None:
        return next((r["value"] for r in body[name] if r["shooter_id"] == sid), None)

    assert value(special, "most_events", hadley) == value(base, "most_events", hadley) + 1
    assert value(special, "most_events", kim) == 1
    assert value(special, "longest_streaks", kim) == 1


def test_the_sundays_board_counts_the_special_sunday(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    url = f"/api/leaderboards?period=ytd&metric=events&as_of={AFTER}"
    base, special = _both(fx_viewer_client, fx_special_viewer_client, url)
    hadley = _id(fx_viewer_client, "Hadley, Ike")
    kim = _id(fx_special_viewer_client, "Kim, Pat")
    before = {r["shooter_id"]: r["value"] for r in base["rows"]}
    after = {r["shooter_id"]: r["value"] for r in special["rows"]}

    assert after[hadley] == before[hadley] + 1
    assert after[kim] == 1
    assert kim not in before
    assert special["event_dates"] == base["event_dates"]  # the scored Sundays


def test_the_sunday_payloads_mark_the_special_sunday(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    base, special = _both(fx_viewer_client, fx_special_viewer_client, "/api/events?year=2026")
    extra = [e for e in special if e["event_date"] == SPECIAL]
    assert [e for e in special if e["event_date"] != SPECIAL] == base
    (row,) = extra
    assert (row["kind"], row["label"], row["target_total"]) == ("special", "Three Clay Shoot", 60)
    assert (row["n_shooters"], row["median"], row["top_score"], row["winners"]) == (5, None, None, [])
    assert {e["kind"] for e in base} == {"regular"}

    clear_cache()
    assert fx_viewer_client.get(f"/api/events/{SPECIAL}").status_code == 404
    clear_cache()
    detail = _get(fx_special_viewer_client, f"/api/events/{SPECIAL}")
    assert (detail["kind"], detail["label"], detail["target_total"]) == (
        "special",
        "Three Clay Shoot",
        60,
    )
    assert [(r["display_name"], r["score"]) for r in detail["results"]] == [
        ("Hadley, Ike", 55),
        ("Kaplan, Noel", 51),
        ("Devlin, Sid", 48),
        ("Abernathy, Preston", 44),
        ("Kim, Pat", 39),
    ]
    assert {(r["event_rank"], r["adjusted"], r["rating_delta"], r["is_best_round"])
            for r in detail["results"]} == {(None, None, None, True)}
    assert [s["label"] for s in detail["stations"]["layout"]] == [str(n) for n in range(1, 11)]
    assert {s["target_count"] for s in detail["stations"]["layout"]} == {6}
    assert sorted(e["total"] for e in detail["stations"]["entries"]) == [39, 44, 48, 51, 55]
    assert [(n["kind"], n["display_name"]) for n in detail["notables"]] == [
        ("first_timer", "Kim, Pat")
    ]
    assert detail["vs_prev"] is None
    assert detail["median"] is None and detail["difficulty"] is None

    base_after, special_after = _both(
        fx_viewer_client, fx_special_viewer_client, f"/api/events/{AFTER}"
    )
    assert special_after == base_after
    assert special_after["vs_prev"]["prev_date"] == BEFORE  # never the special Sunday

    base_rows, special_rows = _both(
        fx_viewer_client, fx_special_viewer_client, "/api/club/attendance"
    )
    assert [r for r in special_rows if r["event_date"] != SPECIAL] == base_rows
    (attendance,) = [r for r in special_rows if r["event_date"] == SPECIAL]
    assert (attendance["kind"], attendance["n_shooters"], attendance["target_total"]) == (
        "special",
        5,
        60,
    )


def test_odometer_counts_the_special_sunday(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    hadley = _id(fx_viewer_client, "Hadley, Ike")
    base, special = _both(fx_viewer_client, fx_special_viewer_client, f"/api/shooters/{hadley}")

    for key in ("clays_thrown", "clays_broken", "hit_pct", "rounds"):  # trophies move (Task 4)
        assert special["odometer"][key] == base["odometer"][key], key
    assert special["odometer"]["events"] == base["odometer"]["events"] + 1
    assert special["odometer"]["years_active"] == base["odometer"]["years_active"]
    assert special["odometer"]["current_streak"] == base["odometer"]["current_streak"] + 1
    assert special["stats"] == base["stats"]
    assert special["pbs"] == base["pbs"]
    clear_cache()
    assert _get(fx_viewer_client, f"/api/shooters/{hadley}/special") == []
    clear_cache()
    assert _get(fx_special_viewer_client, f"/api/shooters/{hadley}/special") == [
        {
            "round_id": special_round_id(fx_special_viewer_client, hadley),
            "event_date": SPECIAL,
            "label": "Three Clay Shoot",
            "target_total": 60,
            "score": 55,
        }
    ]
    base_dir, special_dir = _both(fx_viewer_client, fx_special_viewer_client, "/api/shooters")
    row = {s["shooter_id"]: s for s in special_dir}
    was = {s["shooter_id"]: s for s in base_dir}
    assert row[hadley]["n_events"] == was[hadley]["n_events"] + 1
    assert row[hadley]["n_rounds"] == was[hadley]["n_rounds"]


def special_round_id(client: TestClient, shooter_id: int) -> int:
    detail = _get(client, f"/api/events/{SPECIAL}")
    return next(int(r["round_id"]) for r in detail["results"] if r["shooter_id"] == shooter_id)


def test_a_special_only_shooter_has_a_working_profile(
    fx_special_viewer_client: TestClient,
) -> None:
    client = fx_special_viewer_client
    kim = _id(client, "Kim, Pat")

    (listed,) = [s for s in _get(client, "/api/shooters") if s["shooter_id"] == kim]
    assert (listed["n_rounds"], listed["n_events"], listed["active"], listed["mu"]) == (
        0,
        1,
        False,
        None,
    )
    detail = _get(client, f"/api/shooters/{kim}")
    assert detail["stats"]["n_rounds"] == 0
    assert detail["stats"]["avg_score"] is None and detail["stats"]["best_score"] is None
    odometer = detail["odometer"]
    assert (odometer["events"], odometer["rounds"], odometer["clays_thrown"]) == (1, 0, 0)
    assert odometer["hit_pct"] is None
    assert (odometer["current_streak"], odometer["longest_streak"]) == (0, 1)
    assert detail["pbs"] == []
    assert _get(client, f"/api/shooters/{kim}/rounds") == []
    assert _get(client, f"/api/shooters/{kim}/rating")["points"] == []
    assert _get(client, f"/api/shooters/{kim}/splits?by=year") == []
    insights = _get(client, f"/api/shooters/{kim}/insights")
    assert insights["n_rounds"] == 0
    assert (insights["milestone"]["next_events"], insights["milestone"]["events_to_go"]) == (10, 9)
    assert [s["score"] for s in _get(client, f"/api/shooters/{kim}/special")] == [39]
    assert _get(client, f"/api/yir/2026/shooters/{kim}")["totals"]["events"] == 1
    assert client.get(f"/api/shooters/{kim}/stations").status_code == 200


def test_club_turnout_cohorts_trends_and_year_count_the_special_sunday(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    window = f"/api/club/summary?since=2026-09-01&as_of={AFTER}"
    base, special = _both(fx_viewer_client, fx_special_viewer_client, window)
    for key in ("n_rounds", "avg_score", "median_score", "top_score", "n_perfect",
                "clays_thrown", "clays_broken", "n_scored_events", "first_event", "last_event",
                "avg_head_count", "status_by_year"):
        assert special[key] == base[key], key
    assert special["n_events"] == base["n_events"] + 1
    assert special["n_held_events"] == base["n_held_events"] + 1
    assert special["n_shooters"] == base["n_shooters"] + 1  # Kim, Pat

    base, special = _both(fx_viewer_client, fx_special_viewer_client, "/api/club/cohorts")
    new = {c["year"]: c["n_new"] for c in special}
    old = {c["year"]: c["n_new"] for c in base}
    assert new[2026] == old[2026] + 1
    assert {y: n for y, n in new.items() if y != 2026} == {y: n for y, n in old.items() if y != 2026}

    base, special = _both(fx_viewer_client, fx_special_viewer_client, "/api/club/trends")
    year = {y["year"]: y for y in special["years"]}[2026]
    was = {y["year"]: y for y in base["years"]}[2026]
    assert year["events_held"] == was["events_held"] + 1
    assert year["unique_shooters"] == was["unique_shooters"] + 1
    assert year["ytd_rounds"] == was["ytd_rounds"]
    assert special["events"] == base["events"]
    september = {m["month"]: m for m in special["months"]}[9]
    assert september["n_events"] == {m["month"]: m for m in base["months"]}[9]["n_events"] + 1
    assert september["mean_median"] == {m["month"]: m for m in base["months"]}[9]["mean_median"]

    base, special = _both(fx_viewer_client, fx_special_viewer_client, "/api/yir/2026")
    assert special["totals"]["held_events"] == base["totals"]["held_events"] + 1
    assert special["totals"]["shooters"] == base["totals"]["shooters"] + 1
    for key in ("rounds", "clays_thrown", "clays_broken", "avg_score", "scored_events"):
        assert special["totals"][key] == base["totals"][key], key
    assert special["top_rounds"] == base["top_rounds"]
    assert special["perfect_rounds"] == base["perfect_rounds"]
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/unit/analytics/competition/test_leaderboard_metrics.py tests/unit/analytics/records/test_records_unit.py tests/unit/extras/test_extras_yir.py tests/unit/analytics_core/test_club_insights.py tests/unit/analytics_core/test_shooter_profile.py tests/integration/special/test_special_routes.py`
Expected: FAIL. The unit tests error on the new keyword or positional arguments (`appearances`, `calendar`, `YirFrames(appearances=…)`); the route tests fail on missing `kind`/`label`/`target_total`, the 404 for `/api/events/2026-09-20` in the special world, the missing `/special` route, the unchanged appearance counts, and `held_dates` still listing 2026-09-20; the new tie-key unit test fails because the Sundays board's appearances do not exist yet. The score-route cases already pass (the seam from Task 3); keep them as the guard.

- [ ] **Step 4: Write the analytics changes**

`backend/src/sunday_clays/analytics/leaderboards.py`:

1. Replace

```python
from sunday_clays.analytics.frames import (
    apply_round_type_filter,
    load_events,
    load_rating_history,
    load_rounds,
)
```

with

```python
from sunday_clays.analytics.frames import (
    apply_round_type_filter,
    load_appearances,
    load_events,
    load_rating_history,
    load_rounds,
)
```

2. In `LeaderboardFrames`, after the `shooters: pd.DataFrame` field, add:

```python
    # One row per shooter per Sunday shot, special Sundays included (Plan 17): the Sundays board
    # reads it, and so does the D6 tie key of a shooter with no scored round (_tie_keys).
    # Without special Sundays it is the rounds themselves.
    appearances: pd.DataFrame
```

3. Replace `make_leaderboard_frames` with:

```python
def make_leaderboard_frames(
    rounds: pd.DataFrame,
    events: pd.DataFrame,
    history: pd.DataFrame,
    appearances: pd.DataFrame | None = None,
) -> LeaderboardFrames:
    dated = _normalized_rounds(rounds)
    seen = dated if appearances is None else _with_dates(appearances)
    names = seen.groupby("shooter_id", as_index=False).agg(
        display_name=("display_name", "first"),
        status=("shooter_status", "first"),
    )
    shooters = names.merge(_tie_keys(dated, seen), on="shooter_id", how="left")
    return LeaderboardFrames(
        rounds=dated,
        events=_with_dates(events),
        history=_with_dates(history),
        shooters=shooters,
        appearances=seen,
    )
```

4. Add before `_shooters_as_of`:

```python
def _tie_keys(
    rounds: pd.DataFrame, appearances: pd.DataFrame, as_of: date | None = None
) -> pd.DataFrame:
    """shooter_id, sort_key: the D6 tie key (smallest ``name_key``) from scored rounds; only a
    shooter with no scored round (special Sundays only, Plan 17) takes it from appearances.

    A special sheet's spelling (say an alias-ruled first name that sorts first) therefore never
    reorders tied rows on a score board or on the Sundays board.
    """
    if as_of is not None:
        rounds = rounds[rounds["event_date"] <= as_of]
        appearances = appearances[appearances["event_date"] <= as_of]
    scored = rounds.groupby("shooter_id", as_index=False).agg(sort_key=("name_key", "min"))
    seen = appearances.groupby("shooter_id", as_index=False).agg(sort_key=("name_key", "min"))
    only_seen = seen[~seen["shooter_id"].isin(scored["shooter_id"])]
    return pd.concat([scored, only_seen], ignore_index=True)
```

and in `_shooters_as_of`, replace

```python
    past = frames.rounds[frames.rounds["event_date"] <= as_of]
    keys = past.groupby("shooter_id", as_index=False).agg(sort_key=("name_key", "min"))
```

with

```python
    keys = _tie_keys(frames.rounds, frames.appearances, as_of)
```

and change its docstring's first line to `    """``frames.shooters`` with the D6 tie key taken from rounds (appearances for a shooter with none) on or before ``as_of`` only.`.

5. In `leaderboard`, replace

```python
    if metric is LeaderboardMetric.RATING_GAIN:
        gains = _rating_gain(frames, period, as_of, since)
        body = gains[gains["value"] > 0]  # only gainers: a positive-only board
    else:
```

with

```python
    if metric is LeaderboardMetric.RATING_GAIN:
        gains = _rating_gain(frames, period, as_of, since)
        body = gains[gains["value"] > 0]  # only gainers: a positive-only board
    elif metric is LeaderboardMetric.EVENTS and filters.gauge is None:
        # Sundays shot, special Sundays included (Plan 17); a gauge filter counts scored Sundays
        start, end = period_bounds(period, as_of, since)
        seen = _window(frames.appearances, start, end)
        body = _events(apply_round_type_filter(seen, filters.round_types))
    else:
```

6. In `load_leaderboard_frames`, replace

```python
    return make_leaderboard_frames(
        load_rounds(session), load_events(session), load_rating_history(session)
    )
```

with

```python
    return make_leaderboard_frames(
        load_rounds(session),
        load_events(session),
        load_rating_history(session),
        load_appearances(session),
    )
```

`backend/src/sunday_clays/analytics/records.py`:

1. Add `load_appearances` and `load_calendar` to the `from sunday_clays.analytics.frames import (...)` list.

2. Replace the signature and the start of `compute_records`

```python
    limit: int | None = RECORD_LIMIT,
    since: date | None = None,
) -> Records:
```

with

```python
    limit: int | None = RECORD_LIMIT,
    since: date | None = None,
    appearances: pd.DataFrame | None = None,
    calendar: pd.DataFrame | None = None,
) -> Records:
```

and change its docstring's last line to `    ``limit`` caps every list (``None`` = every row). The perfect 50s list is newest first. "Most Sundays" and "Longest runs" read ``appearances`` and ``calendar`` (special Sundays included, Plan 17); without them the rounds and events stand in.`.

3. Replace

```python
    attended = past_rounds.groupby("shooter_id", as_index=False).agg(
        value=("event_date", "nunique")
    )
    streak = streaks(past_rounds, past_events, as_of)
```

with

```python
    seen = _with_dates(rounds if appearances is None else appearances)
    seen_upto = seen[seen["event_date"] <= as_of]
    sunday_names = seen_upto.groupby("shooter_id", as_index=False).agg(
        display_name=("display_name", "first"), sort_key=("name_key", "min")
    )
    every_sunday = _with_dates(events if calendar is None else calendar)
    past_seen = in_range(apply_round_type_filter(seen_upto, round_types))
    past_calendar = in_range(
        apply_round_type_filter(every_sunday[every_sunday["event_date"] <= as_of], round_types)
    )
    attended = past_seen.groupby("shooter_id", as_index=False).agg(
        value=("event_date", "nunique")
    )
    streak = streaks(past_seen, past_calendar, as_of)
```

and replace

```python
    attendance = _shooter_records(attended, names, limit)
    runs = _shooter_records(longest, names, limit)
```

with

```python
    attendance = _shooter_records(attended, sunday_names, limit)
    runs = _shooter_records(longest, sunday_names, limit)
```

4. In `records_for`, replace

```python
        as_of=as_of,
        round_types=round_types,
        since=since,
        limit=limit,
    )
```

with

```python
        as_of=as_of,
        round_types=round_types,
        since=since,
        limit=limit,
        appearances=load_appearances(session),
        calendar=load_calendar(session),
    )
```

`backend/src/sunday_clays/analytics/club_insights.py`, replace `yearly_trends` with:

```python
def yearly_trends(
    rounds: pd.DataFrame,
    events: pd.DataFrame,
    as_of: date,
    appearances: pd.DataFrame | None = None,
) -> list[YearTrend]:
    """Per calendar year up to as_of; the YTD window ends on as_of's month/day.

    Pass the calendar as `events` and the appearance frame as `appearances` (Plan 17): Sundays
    held, head counts and unique shooters then count special Sundays; ytd_rounds stays the
    scored rounds.
    """
    held = list(_held_events(events, as_of)["event_date"])
    upto = rounds.loc[rounds["event_date"] <= as_of]
    seen = upto if appearances is None else appearances.loc[appearances["event_date"] <= as_of]
    heads = events.loc[events["event_date"] <= as_of]
    years = sorted({d.year for d in heads["event_date"]} | {d.year for d in seen["event_date"]})
    out: list[YearTrend] = []
    ytd_by_year: dict[int, int] = {}
    for year in years:
        cutoff = _ytd_cutoff(year, as_of)
        in_year = upto.loc[[d.year == year for d in upto["event_date"]]]
        seen_year = seen.loc[[d.year == year for d in seen["event_date"]]]
        ytd = in_year.loc[in_year["event_date"] <= cutoff]
        seen_ytd = seen_year.loc[seen_year["event_date"] <= cutoff]
        head_counts = heads.loc[
            [d.year == year for d in heads["event_date"]], "head_count"
        ].dropna()
        ytd_events = sum(1 for d in held if d.year == year and d <= cutoff)
        previous_ytd = ytd_by_year.get(year - 1, 0)  # a year absent from `years` held none
        out.append(
            YearTrend(
                year=year,
                events_held=sum(1 for d in held if d.year == year),
                mean_head_count=None if head_counts.empty else float(head_counts.mean()),
                unique_shooters=int(seen_year["shooter_id"].nunique()),
                ytd_events=ytd_events,
                ytd_rounds=len(ytd),
                ytd_unique_shooters=int(seen_ytd["shooter_id"].nunique()),
                ytd_events_yoy=None
                if previous_ytd == 0
                else (ytd_events - previous_ytd) / previous_ytd,
            )
        )
        ytd_by_year[year] = ytd_events
    return out
```

`backend/src/sunday_clays/analytics/profile.py`, replace

```python
def shooter_insights(
    rounds: pd.DataFrame,
    history: pd.DataFrame,
    shooters: pd.DataFrame,
    shooter_id: int,
    as_of: date,
) -> ShooterInsights:
    """Everything is computed from rows dated <= as_of (no-leak)."""
```

with

```python
def shooter_insights(
    rounds: pd.DataFrame,
    history: pd.DataFrame,
    shooters: pd.DataFrame,
    shooter_id: int,
    as_of: date,
    appearances: pd.DataFrame | None = None,
) -> ShooterInsights:
    """Everything is computed from rows dated <= as_of (no-leak).

    The Sundays milestone counts `appearances` (special Sundays included, Plan 17) when given.
    """
```

and replace `        milestone=milestone(set(mine["event_date"]), as_of),` with

```python
        milestone=milestone(set(_sundays_shot(mine, appearances, shooter_id, as_of)), as_of),
```

adding above `shooter_insights`:

```python
def _sundays_shot(
    mine: pd.DataFrame, appearances: pd.DataFrame | None, shooter_id: int, as_of: date
) -> pd.Series:
    if appearances is None:
        return mine["event_date"]
    seen = _upto(appearances, as_of)
    return seen.loc[seen["shooter_id"] == shooter_id, "event_date"]
```

`backend/src/sunday_clays/analytics/yir.py`:

1. Replace

```python
_EVENTS_SQL: Final = """
SELECT e.event_date, e.round_type, e.has_scores, e.results_complete, e.head_count, e.n_shooters,
       m.median, m.top_score, m.difficulty
FROM events AS e
```

with

```python
_EVENTS_SQL: Final = """
SELECT e.event_date, e.round_type, e.has_scores, e.results_complete, e.head_count, e.n_shooters,
       m.median, m.top_score, m.difficulty, e.kind
FROM events AS e
```

and add `"kind",` as the last entry of `_EVENT_COLUMNS`.

2. Replace

```python
@dataclass(frozen=True)
class YirFrames:
    rounds: pd.DataFrame  # event_date, round_type, shooter_id, display_name, score, ...
    events: pd.DataFrame  # _EVENT_COLUMNS
    profiles: pd.DataFrame  # shooter_id, display_name, left_censored
    trophies: pd.DataFrame  # shooter_id, code, event_date
    history: pd.DataFrame  # shooter_id, event_date, mu
```

with

```python
@dataclass(frozen=True)
class YirFrames:
    rounds: pd.DataFrame  # event_date, round_type, shooter_id, display_name, score, ... (regular)
    events: pd.DataFrame  # _EVENT_COLUMNS: every Sunday, special ones included (kind)
    profiles: pd.DataFrame  # shooter_id, display_name, left_censored
    trophies: pd.DataFrame  # shooter_id, code, event_date
    history: pd.DataFrame  # shooter_id, event_date, mu
    # event_date, round_type, shooter_id per Sunday shot, special included (Plan 17)
    appearances: pd.DataFrame | None = None

    @property
    def sundays_shot(self) -> pd.DataFrame:
        """Who shot which Sunday, special Sundays included; the rounds when not given."""
        return self.rounds if self.appearances is None else self.appearances


def _regular(events: pd.DataFrame) -> pd.DataFrame:
    """Regular Sundays only; a frame without `kind` is all regular."""
    return events if "kind" not in events.columns else events[events["kind"].eq("regular")]
```

3. In `year_totals`, replace

```python
    return YearTotals(
        year=year,
        scored_events=int(events["has_scores"].sum()),
        held_events=int(events["results_complete"].sum()),
        rounds=len(rounds),
        shooters=int(rounds["shooter_id"].nunique()),
```

with

```python
    seen = data.sundays_shot[_in_year(data.sundays_shot["event_date"], year)]
    return YearTotals(
        year=year,
        scored_events=int(_regular(events)["has_scores"].sum()),
        held_events=int(events["results_complete"].sum()),
        rounds=len(rounds),
        shooters=int(seen["shooter_id"].nunique()),
```

4. In `club_year`, replace

```python
    firsts = data.rounds.groupby("shooter_id")["event_date"].min()
```

with

```python
    firsts = data.sundays_shot.groupby("shooter_id")["event_date"].min()
    seen_months = _months(data.sundays_shot[_in_year(data.sundays_shot["event_date"], year)])
```

and replace

```python
        MonthStat(
            month=m,
            events=int(group["event_date"].nunique()),
```

with

```python
        MonthStat(
            month=m,
            events=int(seen_months[m]["event_date"].nunique()),
```

5. Replace `_shooter_totals` with:

```python
def _shooter_totals(
    rounds: pd.DataFrame, year: int, sundays: pd.DataFrame | None = None
) -> ShooterTotals:
    mine = rounds[_in_year(rounds["event_date"], year)]
    seen = mine if sundays is None else sundays[_in_year(sundays["event_date"], year)]
    return ShooterTotals(
        year=year,
        events=int(seen["event_date"].nunique()),
        rounds=len(mine),
        clays_thrown=TARGETS_PER_ROUND * len(mine),
        clays_broken=int(mine["score"].sum()),
        avg_score=_mean(mine["score"]),
    )
```

6. In `shooter_year`, replace

```python
    events_by_shooter = year_rounds.groupby("shooter_id")["event_date"].nunique()
    my_events = int(mine["event_date"].nunique())
```

with

```python
    seen = data.sundays_shot
    my_sundays = seen[seen["shooter_id"] == shooter_id]
    year_seen = seen[_in_year(seen["event_date"], year)]
    events_by_shooter = year_seen.groupby("shooter_id")["event_date"].nunique()
    my_events = int(my_sundays[_in_year(my_sundays["event_date"], year)]["event_date"].nunique())
```

replace `    previous = _shooter_totals(all_mine, year - 1)` with `    previous = _shooter_totals(all_mine, year - 1, my_sundays)`, and `        totals=_shooter_totals(all_mine, year),` with `        totals=_shooter_totals(all_mine, year, my_sundays),`.

7. In `on_this_day`, replace `    events = data.events` with `    events = _regular(data.events)  # quotes scores: regular Sundays only`.

8. In `filter_round_types`, replace

```python
    return replace(
        data,
        rounds=frames.apply_round_type_filter(data.rounds, round_types),
        events=events,
        trophies=data.trophies[data.trophies["event_date"].isin(kept)],
    )
```

with

```python
    return replace(
        data,
        rounds=frames.apply_round_type_filter(data.rounds, round_types),
        events=events,
        trophies=data.trophies[data.trophies["event_date"].isin(kept)],
        appearances=None
        if data.appearances is None
        else frames.apply_round_type_filter(data.appearances, round_types),
    )
```

9. In `scored_years`, replace `    scored = data.events[data.events["has_scores"]]` with `    scored = _regular(data.events)[lambda e: e["has_scores"]]`.

10. In `load_yir_frames`, before `return YirFrames(`, add:

```python
    appearances = frames.load_appearances(session)[["event_date", "round_type", "shooter_id"]].copy()
    appearances["event_date"] = _as_dates(appearances["event_date"])
```

and pass `appearances=appearances` to `YirFrames(...)`.

- [ ] **Step 5: Write the route changes**

`backend/src/sunday_clays/api/routes/events.py`:

1. After `PB_MIN_PRIOR_ROUNDS = 5`, add:

```python
EventKind = Literal["regular", "special"]
```

2. In `EventSummaryOut`, after `    winners: list[WinnerOut]`, add:

```python
    # Plan 17: a special Sunday counts only as an appearance; its own name and target total
    kind: EventKind = "regular"
    label: str | None = None
    target_total: int = frames.REGULAR_TARGETS
```

and in `EventDetailOut`, after `    vs_prev: VsPrevOut | None`, add the same three lines.

3. Add after `_winners`:

```python
def _kind(row: dict[str, Any]) -> EventKind:
    return "special" if row["kind"] == frames.EVENT_KIND_SPECIAL else "regular"
```

4. In `list_events`, replace `    events = frames.apply_round_type_filter(frames.load_events(session), round_types)` with `    events = frames.apply_round_type_filter(frames.load_calendar(session), round_types)`, and in the `EventSummaryOut(...)` call add after `winners=winners.get(row["event_date"], []),`:

```python
            kind=_kind(row),
            label=opt_str(row["label"]),
            target_total=int(row["target_total"]),
```

5. Add after `_results`:

```python
def _special_results(special: pd.DataFrame, event_date: date) -> list[EventResultOut]:
    """A special Sunday's rounds, best first: as entered, never ranked or rated (Decision 18)."""
    day = special.loc[special["event_date"] == event_date]
    ordered = day.sort_values(["score", "display_name", "ordinal"], ascending=[False, True, True])
    return [
        EventResultOut(
            round_id=int(r["round_id"]),
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            name_key=str(r["name_key"]),
            shooter_status=str(r["shooter_status"]),
            ordinal=int(r["ordinal"]),
            score=int(r["score"]),
            gauge_class=None,
            is_best_round=True,
            event_rank=None,
            percentile=None,
            adjusted=None,
            expected=None,
            residual=None,
            mu_before=None,
            mu_after=None,
            rating_delta=None,
        )
        for r in rows(ordered)
    ]
```

6. Replace the body of `get_event` from `    events = frames.load_events(session)` to its `return` statement's end with:

```python
    events = frames.load_calendar(session)
    match = events.loc[events["event_date"] == event_date]
    if match.empty:
        raise NotFoundError("event_not_found", f"No event on {event_date.isoformat()}")
    event = rows(match)[0]
    special = _kind(event) == "special"
    rounds = frames.load_rounds(session)
    shooters = frames.load_shooters(session)
    hits = (
        frames.load_special_station_hits(session)
        if special
        else frames.load_station_hits(session)
    )
    names = {int(r["shooter_id"]): str(r["display_name"]) for r in rows(shooters)}
    results = (
        _special_results(frames.load_special_rounds(session), event_date)
        if special
        else _results(rounds.loc[rounds["event_date"] == event_date])
    )
    regular = events.loc[events["kind"] == frames.EVENT_KIND_REGULAR]
    return EventDetailOut(
        event_date=event_date,
        round_type=RoundType(str(event["round_type"])),
        round_type_source=str(event["round_type_source"]),
        head_count=opt_int(event["head_count"]),
        has_scores=bool(event["has_scores"]),
        has_stations=bool(event["has_stations"]),
        results_complete=bool(event["results_complete"]),
        n_rounds=int(event["n_rounds"]),
        n_shooters=int(event["n_shooters"]),
        median=opt_float(event["median"]),
        mean=opt_float(event["mean"]),
        stdev=opt_float(event["stdev"]),
        top_score=opt_int(event["top_score"]),
        difficulty=opt_float(event["difficulty"]),
        results=results,
        weather=_weather(event),
        stations=_stations(hits.loc[hits["event_date"] == event_date], names),
        notables=event_notables(rounds, shooters, event_date),
        vs_prev=None if special else _vs_prev(regular, event),
        kind=_kind(event),
        label=opt_str(event["label"]),
        target_total=int(event["target_total"]),
    )
```

`backend/src/sunday_clays/api/routes/shooters.py`:

1. Add `from collections.abc import Collection` to the imports.

2. Replace

```python
def odometer(rounds: pd.DataFrame, streak_row: dict[str, Any] | None, trophies: int) -> OdometerOut:
    """Lifetime counters over all of one shooter's rounds (C12 odometer)."""
    thrown = len(rounds) * TARGETS_PER_ROUND
    broken = int(rounds["score"].sum())
    dates = sorted(set(rounds["event_date"]))
```

with

```python
def odometer(
    rounds: pd.DataFrame,
    streak_row: dict[str, Any] | None,
    trophies: int,
    sundays: Collection[date] | None = None,
) -> OdometerOut:
    """Lifetime counters (C12 odometer): clays from the scored rounds; Sundays, years and the
    favourite month from `sundays` (every Sunday shot, special ones included, Plan 17)."""
    thrown = len(rounds) * TARGETS_PER_ROUND
    broken = int(rounds["score"].sum())
    dates = sorted(set(rounds["event_date"]) if sundays is None else set(sundays))
```

3. In `get_shooter`, replace

```python
    # Streaks are per shooter, so this shooter's lifetime rounds give the same row as
    # streaks(all_rounds, ...) at a fraction of the work.
    streak_rows = rows(streaks(lifetime, frames.load_events(session), today))
```

with

```python
    # Streaks are per shooter, so this shooter's Sundays give the same row as streaks over
    # everyone at a fraction of the work. Special Sundays extend runs (Plan 17).
    appearances = frames.load_appearances(session)
    my_sundays = appearances.loc[appearances["shooter_id"] == shooter_id]
    streak_rows = rows(streaks(my_sundays, frames.load_calendar(session), today))
```

and replace

```python
        odometer=odometer(lifetime, streak_rows[0] if streak_rows else None, trophies),
```

with

```python
        odometer=odometer(
            lifetime,
            streak_rows[0] if streak_rows else None,
            trophies,
            set(my_sundays["event_date"]),
        ),
```

4. After `SplitOut`, add:

```python
class SpecialRoundOut(BaseModel):
    round_id: int
    event_date: date
    label: str
    target_total: int
    score: int
```

and after `get_shooter_rounds`, add:

```python
@router.get("/api/shooters/{id}/special")
def get_shooter_special(shooter_id: ShooterId, session: SessionDep) -> list[SpecialRoundOut]:
    """The shooter's special Sundays (Plan 17), oldest first: appearances, never score stats."""
    _profile(session, shooter_id)
    special = frames.load_special_rounds(session)
    mine = special.loc[special["shooter_id"] == shooter_id].sort_values(
        ["event_date", "ordinal"], kind="mergesort"
    )
    return [
        SpecialRoundOut(
            round_id=int(r["round_id"]),
            event_date=r["event_date"],
            label=str(r["label"]),
            target_total=int(r["target_total"]),
            score=int(r["score"]),
        )
        for r in rows(mine)
    ]
```

`backend/src/sunday_clays/api/routes/shooter_insights.py`, replace

```python
        shooter_id,
        day,
    )
```

with

```python
        shooter_id,
        day,
        frames.load_appearances(session),
    )
```

`backend/src/sunday_clays/api/routes/club.py`:

1. In `AttendanceOut`, after `    results_complete: bool`, add:

```python
    kind: Literal["regular", "special"] = "regular"  # Plan 17
    label: str | None = None
    target_total: int = frames.REGULAR_TARGETS
```

2. Replace the body of `club_summary` from `    check_window(since, as_of)` to its `return ClubSummaryOut(` line (exclusive) with:

```python
    check_window(since, as_of)
    every_round = frames.apply_round_type_filter(frames.load_rounds(session), round_types)
    # Sundays, held Sundays, shooters and head counts include special Sundays (Plan 17); every
    # score number, n_scored_events and first/last_event are regular Sundays only.
    calendar = in_window(
        frames.apply_round_type_filter(frames.load_calendar(session), round_types), since, as_of
    )
    seen = in_window(
        frames.apply_round_type_filter(frames.load_appearances(session), round_types), since, as_of
    )
    rounds = in_window(every_round, since, as_of)
    regular = calendar.loc[calendar["kind"] == frames.EVENT_KIND_REGULAR]
    scored = regular.loc[regular["has_scores"]]
    shooters = seen.drop_duplicates("shooter_id")
    by_status = shooters["shooter_status"].value_counts()
    scores = rounds["score"]
```

and inside the `ClubSummaryOut(...)` call replace

```python
        n_events=len(events),
        n_scored_events=len(scored),
        n_held_events=int(events["results_complete"].sum()),
```

with

```python
        n_events=len(calendar),
        n_scored_events=len(scored),
        n_held_events=int(calendar["results_complete"].sum()),
```

and `        avg_head_count=opt_float(events["head_count"].mean()),` with `        avg_head_count=opt_float(calendar["head_count"].mean()),`.

3. In `club_attendance`, change the docstring to `"""Every Sunday (attendance-only and special ones included), date ascending."""`, add to the `AttendanceOut(...)` call

```python
            kind="special" if r["kind"] == frames.EVENT_KIND_SPECIAL else "regular",
            label=opt_str(r["label"]),
            target_total=int(r["target_total"]),
```

and replace `        for r in rows(frames.load_events(session))` with `        for r in rows(frames.load_calendar(session))`. Add `opt_str` to the `_convert` import.

4. In `club_cohorts`, replace `    table, returns = cohort_tables(frames.load_rounds(session), frames.load_shooters(session))` with

```python
    # cohorts follow Sundays shot, so a first Sunday at a special shoot starts a cohort (Plan 17)
    table, returns = cohort_tables(frames.load_appearances(session), frames.load_shooters(session))
```

`backend/src/sunday_clays/api/routes/club_insights.py`, in `get_trends`, replace

```python
    rounds, events = frames.load_rounds(session), frames.load_events(session)
    return ClubTrendsOut(
        as_of=as_of,
        years=[
            YearTrendOut.model_validate(asdict(y))
            for y in club_insights.yearly_trends(rounds, events, as_of)
        ],
```

with

```python
    rounds, events = frames.load_rounds(session), frames.load_events(session)
    calendar, seen = frames.load_calendar(session), frames.load_appearances(session)
    return ClubTrendsOut(
        as_of=as_of,
        years=[
            YearTrendOut.model_validate(asdict(y))
            for y in club_insights.yearly_trends(rounds, calendar, as_of, seen)
        ],
```

and replace

```python
            for m in club_insights.seasonality(events, as_of)
```

with

```python
            for m in club_insights.seasonality(calendar, as_of)  # Sundays and head counts
```

`backend/src/sunday_clays/api/routes/insights.py`: add `from sunday_clays.analytics.frames import EVENT_KIND_REGULAR` to the imports and replace `held_dates` with:

```python
def held_dates(session: Session) -> list[date]:
    """Regular held Sundays, oldest first: every feed's reference Sunday, the home window and
    expiry. A special Sunday is left out, as in `InsightFrames.sundays` (Plan 17, Decision 12)."""
    events = Base.metadata.tables["events"]
    query = (
        select(events.c.event_date)
        .where(events.c.results_complete, events.c.kind == EVENT_KIND_REGULAR)
        .order_by(events.c.event_date)
    )
    return list(session.scalars(query))
```

`sunday_insights_feed` keeps its own lookup: a special Sunday's page asks for its feed, and that feed is simply empty (no insight anchors on it).

- [ ] **Step 6: Run them to verify they pass**

Run: `cd backend && uv run ruff format src tests && uv run pytest -q tests/unit/analytics tests/unit/extras tests/unit/analytics_core tests/integration/special tests/integration/analytics_core tests/integration/api tests/integration/extras tests/integration/insights`
Expected: all pass, the existing route tests unchanged (the regular world answers as before, with `kind: "regular"`, `label: null`, `target_total: 50` added to the Sunday payloads).

- [ ] **Step 7: Gates, OpenAPI export and the full backend suite with coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest -q --cov --cov-branch`
Expected: all green, coverage at or above 90% lines and branches. `tests/unit/api/test_export_openapi.py` and the route auth matrix pick up `/api/shooters/{id}/special` (401 without a viewer).

- [ ] **Step 8: Commit**

```bash
git add backend/src/sunday_clays/api/routes/events.py backend/src/sunday_clays/api/routes/shooters.py backend/src/sunday_clays/api/routes/shooter_insights.py backend/src/sunday_clays/api/routes/club.py backend/src/sunday_clays/api/routes/club_insights.py backend/src/sunday_clays/api/routes/insights.py backend/src/sunday_clays/analytics/leaderboards.py backend/src/sunday_clays/analytics/records.py backend/src/sunday_clays/analytics/yir.py backend/src/sunday_clays/analytics/club_insights.py backend/src/sunday_clays/analytics/profile.py backend/tests/unit/analytics/competition/test_leaderboard_metrics.py backend/tests/unit/analytics/records/test_records_unit.py backend/tests/unit/extras/test_extras_yir.py backend/tests/unit/analytics_core/test_club_insights.py backend/tests/unit/analytics_core/test_shooter_profile.py backend/tests/integration/special/test_special_routes.py
git commit -m "feat(special): Sunday payloads, /special, appearance boards and club turnout (Plan 17 T5)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The special Sunday on screen: list, calendar, Sunday page, profile card and attendance calendar

Everything a viewer sees of a special Sunday. The Sundays list and calendar mark it, its page shows its results and station grid under "Three Clay Shoot · Special · 60 targets", the profile gets a "Special shoots" card, and the attendance calendar and "Sundays shot per month" count it as a Sunday shot without putting its score on the 50-point colour scale.

**Files:**
- Modify: `frontend/src/features/events/format.ts`, `format.test.ts`
- Modify: `frontend/src/features/events/explainers.ts`
- Modify: `frontend/src/features/events/mocks.ts`
- Modify: `frontend/src/features/events/components/EventList.tsx`, `EventList.test.tsx`
- Modify: `frontend/src/features/events/components/SeasonCalendar.tsx`, `SeasonCalendar.test.tsx`
- Create: `frontend/src/features/events/components/SpecialResultsTable.tsx`, `SpecialResultsTable.test.tsx`
- Create: `frontend/src/features/events/components/SpecialShootsCard.tsx`, `SpecialShootsCard.test.tsx`
- Create: `frontend/src/features/events/profileSection.tsx`, `profileSection.test.ts`
- Modify: `frontend/src/features/events/pages/EventDetailPage.tsx`, `EventDetailPage.test.tsx`
- Modify: `frontend/src/features/shooters/api.ts`, `frontend/src/features/shooters/mocks.ts`
- Modify: `frontend/src/features/shooters/charts.ts`, `frontend/src/features/shooters/charts.test.ts`
- Modify: `frontend/src/features/shooters/explainers.ts`
- Modify: `frontend/src/features/shooters/components/ProfileCharts.tsx`, `ProfileCharts.test.tsx`
- Modify: `frontend/src/components/charts/builders/sundayCalendar.ts`, `sundayCalendar.test.ts`

**Interfaces:**
- Consumes (Task 5, through `pnpm gen:api`): `EventSummary`/`EventDetail` fields `kind?: 'regular' | 'special'`, `label?: string | null`, `target_total?: number`; `GET /api/shooters/{id}/special` → `{round_id, event_date, label, target_total, score}[]`, oldest first. A special Sunday's `results` carry `null` metrics and `event_rank: null`; its `median`, `top_score` and `difficulty` are `null`; `vs_prev` is `null`.
- Produces (Task 8 relies on these strings):
  - `events/format.ts`: `isSpecial(e)`, `targetsOf(e)` (`target_total ?? 50`), `specialTag(e)` → `"Special · 60"`, `specialName(e)` (label, or `null`).
  - List line `"Three Clay Shoot · Special · 60 · 5 shooters"`; calendar cell label `"Sep 20, 2026 — Three Clay Shoot, special shoot, 5 shooters"`; legend entry `"Special shoot"`.
  - Sunday page: header line `"Three Clay Shoot · Special · 60 targets"`, a `role="note"` starting `"A special shoot counts as a Sunday shot"`, stats `Shooters`/`Targets`/`Stations`, table `Results` with columns `Shooter` and `Score (of 60)` (explainer toggle `"About special shoots"`), the `Station hits` chart, no `vs previous Sunday` card.
  - Profile: a `Special shoots` card (list `Special shoots`, items `"Sep 20, 2026"`, `"Three Clay Shoot · Special · 60"`, `"55 of 60"`); `shooters/api.ts` `useShooterSpecials(id)` and type `SpecialRound`.
  - Attendance calendar: rows with state `special` (score blank); a heatmap series `"Special"`; `shotDateOf` accepts it; empty text `"No Sundays shot yet"`.

- [ ] **Step 1: Write the failing format, list and calendar tests**

Append to `frontend/src/features/events/format.test.ts` (add `isSpecial, specialName, specialTag, targetsOf` to its import from `./format`):

```ts
describe('special Sundays (Plan 17)', () => {
  it('knows a special Sunday by its kind; an older payload without one is regular', () => {
    expect(isSpecial({ kind: 'special' })).toBe(true);
    expect(isSpecial({ kind: 'regular' })).toBe(false);
    expect(isSpecial({})).toBe(false);
  });

  it('tags a special Sunday with its own target total, 50 when none is sent', () => {
    expect(targetsOf({ target_total: 60 })).toBe(60);
    expect(targetsOf({})).toBe(50);
    expect(specialTag({ target_total: 60 })).toBe('Special · 60');
    expect(specialTag({})).toBe('Special · 50');
  });

  it('names a special Sunday by its label, or not at all', () => {
    expect(specialName({ label: 'Three Clay Shoot' })).toBe('Three Clay Shoot');
    expect(specialName({ label: '  ' })).toBeNull();
    expect(specialName({ label: null })).toBeNull();
    expect(specialName({})).toBeNull();
  });
});
```

Append to the `describe('summaryLine', …)` block in `frontend/src/features/events/components/EventList.test.tsx`:

```tsx
  it.each([
    [
      summary({
        kind: 'special',
        label: 'Three Clay Shoot',
        target_total: 60,
        n_shooters: 40,
        median: null,
        top_score: null,
      }),
      'Three Clay Shoot · Special · 60 · 40 shooters',
    ],
    [summary({ kind: 'special', label: null, target_total: 60, n_shooters: 40 }), 'Special · 60 · 40 shooters'],
  ])('a special Sunday reads by its name and targets, never a median or top score (%#)', (event, want) => {
    expect(summaryLine(event)).toBe(want);
  });
```

In `frontend/src/features/events/components/SeasonCalendar.test.tsx`, replace the legend expectation

```tsx
    expect(items.map((li) => li.lastChild?.textContent)).toEqual([
      'Scored',
      'No scores',
      'Other round type',
      'No Sunday on file',
    ]);
```

with

```tsx
    expect(items.map((li) => li.lastChild?.textContent)).toEqual([
      'Scored',
      'No scores',
      'Special shoot',
      'Other round type',
      'No Sunday on file',
    ]);
```

and append inside its top-level `describe`, adding `cellLabel` to the import from `./SeasonCalendar` and `specialSummary` to the import from `../mocks`:

```tsx
  it('marks a special Sunday with an accent square that names it', () => {
    renderWithProviders(<SeasonCalendar year={2026} events={[specialSummary]} />);
    const cell = screen.getByRole('link', {
      name: 'Sep 20, 2026 — Three Clay Shoot, special shoot, 5 shooters',
    });
    expect(cell).toHaveAttribute('href', '/events/2026-09-20');
    expect(cell.className).toContain('border-accent');
    expect(cell.className).not.toContain('bg-primary');
  });

  it('labels a special Sunday without a name by what it is', () => {
    expect(cellLabel({ ...specialSummary, label: null })).toBe(
      'Sep 20, 2026 — special shoot, 5 shooters',
    );
  });
```

Run: `cd frontend && pnpm gen:api && pnpm exec vitest run src/features/events/format.test.ts src/features/events/components/EventList.test.tsx src/features/events/components/SeasonCalendar.test.tsx`
Expected: FAIL. The format tests fail on `isSpecial is not a function` (not exported); `summaryLine` returns `"40 shooters · Sporting"` and `"40 shooters · Super Sporting · median 34 · top 42"`; the legend lacks `Special shoot`; `specialSummary` is not exported from `../mocks`.

- [ ] **Step 2: Implement the format helpers, the mocks, the list line and the calendar cell**

Append to `frontend/src/features/events/format.ts`:

```ts
/** Regular Sundays are out of 50 (the weekly workbook's rounds). */
const REGULAR_TARGETS = 50;

/** Plan 17: a special shoot. Payloads from before Plan 17 omit `kind`; they are regular. */
export function isSpecial(e: { kind?: string }): boolean {
  return e.kind === 'special';
}

/** Targets a round on this Sunday is out of. */
export function targetsOf(e: { target_total?: number }): number {
  return e.target_total ?? REGULAR_TARGETS;
}

/** "Special · 60": the tag a special shoot carries wherever it is listed. */
export function specialTag(e: { target_total?: number }): string {
  return `Special · ${targetsOf(e)}`;
}

/** The special shoot's name ("Three Clay Shoot"), or null when the sheet gave none. */
export function specialName(e: { label?: string | null }): string | null {
  const label = e.label?.trim() ?? '';
  return label === '' ? null : label;
}
```

Append to `frontend/src/features/events/mocks.ts`, after `attendanceOnlyDetail` (they are **not** added to `eventSummaries`, whose counts other tests assert):

```ts
/** Plan 17: the special Sunday (invented names, as everywhere in tests). */
export const specialSummary: EventSummary = {
  ...stationWeek,
  round_type_source: 'none',
  event_date: '2026-09-20',
  round_type: 'sporting',
  head_count: null,
  n_rounds: 5,
  n_shooters: 5,
  median: null,
  top_score: null,
  difficulty: null,
  winners: [],
  kind: 'special',
  label: 'Three Clay Shoot',
  target_total: 60,
};

const asEntered = {
  ...noModel,
  ordinal: 1,
  adjusted: null,
  event_rank: null,
  is_best_round: true,
  percentile: null,
  mu_before: null,
  mu_after: null,
  rating_delta: null,
} as const;

/** One hit count per station 1..10 (6 targets each) → the API's cells. */
function specialCells(hits: number[]): StationMatrix['entries'][number]['hits'] {
  return hits.map((h, i) => ({ label: String(i + 1), station_no: i + 1, hits: h }));
}

const SPECIAL_SHOOTERS = [
  { round_id: 9001, shooter_id: 3, display_name: 'Hadley, Ike', name_key: 'hadley ike', hits: [6, 5, 6, 4, 6, 5, 6, 6, 5, 6] },
  { round_id: 9002, shooter_id: 18, display_name: 'Kaplan, Noel', name_key: 'kaplan noel', hits: [6, 5, 5, 5, 6, 5, 5, 5, 4, 5] },
  { round_id: 9003, shooter_id: 340, display_name: 'Kim, Pat', name_key: 'kim pat', hits: [4, 4, 3, 4, 4, 4, 4, 4, 4, 4] },
] as const;

export const specialDetail: EventDetail = {
  event_date: '2026-09-20',
  round_type: 'sporting',
  round_type_source: 'none',
  head_count: null,
  has_scores: true,
  has_stations: true,
  results_complete: true,
  n_rounds: 3,
  n_shooters: 3,
  median: null,
  mean: null,
  stdev: null,
  top_score: null,
  difficulty: null,
  // The server sends them best first; the table sorts anyway, so list them out of order here.
  results: [SPECIAL_SHOOTERS[2], SPECIAL_SHOOTERS[0], SPECIAL_SHOOTERS[1]].map((s) => ({
    ...asEntered,
    round_id: s.round_id,
    shooter_id: s.shooter_id,
    display_name: s.display_name,
    name_key: s.name_key,
    score: s.hits.reduce((a, b) => a + b, 0),
  })),
  weather: null,
  stations: {
    layout: Array.from({ length: 10 }, (_, i) => ({
      label: String(i + 1),
      station_no: i + 1,
      target_count: 6,
    })),
    entries: SPECIAL_SHOOTERS.map((s, i) => ({
      entry_row: i + 5,
      name_key: s.name_key,
      shooter_id: s.shooter_id,
      display_name: s.display_name,
      round_id: s.round_id,
      hits: specialCells([...s.hits]),
      total: s.hits.reduce((a, b) => a + b, 0),
    })),
  },
  notables: [
    { kind: 'first_timer', shooter_id: 340, display_name: 'Kim, Pat', detail: 'First Sunday', value: null },
  ],  // the server lists first-timers; the page leaves them to insights (NotablesCard)
  vs_prev: null,
  kind: 'special',
  label: 'Three Clay Shoot',
  target_total: 60,
};
```

In `frontend/src/features/events/components/EventList.tsx`, change the import from `../format` to `import { formatDay, formatScore, roundTypeLabel, isSpecial, specialName, specialTag } from '../format';` and make `summaryLine` start with the special case:

```tsx
export function summaryLine(e: EventSummary): string {
  if (isSpecial(e)) {
    const name = specialName(e);
    return [...(name === null ? [] : [name]), specialTag(e), `${e.n_shooters} shooters`].join(' · ');
  }
  if (!e.has_scores) {
```

(the rest of the function is unchanged).

In `frontend/src/features/events/components/SeasonCalendar.tsx`:

1. Replace `import { formatDay } from '../format';` with `import { formatDay, isSpecial, specialName } from '../format';`.
2. Replace the `CELL_STYLES` and `LEGEND` constants with:

```tsx
const CELL_STYLES = {
  scored: 'bg-primary text-text',
  unscored: 'border border-outline-variant text-text-muted',
  special: 'border-2 border-accent text-text',
  empty: 'opacity-40',
  other: 'border border-dashed border-outline-variant text-text-muted',
} as const;

const LEGEND: { state: keyof typeof CELL_STYLES; label: string }[] = [
  { state: 'scored', label: 'Scored' },
  { state: 'unscored', label: 'No scores' },
  { state: 'special', label: 'Special shoot' },
  { state: 'other', label: 'Other round type' },
  { state: 'empty', label: 'No Sunday on file' },
];

/** A Sunday on file: a special shoot, scored, or met without scores. */
function cellState(e: EventSummary): 'special' | 'scored' | 'unscored' {
  if (isSpecial(e)) return 'special';
  return e.has_scores ? 'scored' : 'unscored';
}
```

3. Make `cellLabel` start with:

```tsx
export function cellLabel(e: EventSummary): string {
  if (isSpecial(e)) {
    const name = specialName(e);
    return `${formatDay(e.event_date)} — ${name === null ? '' : `${name}, `}special shoot, ${e.n_shooters} shooters`;
  }
  if (e.has_scores) return `${formatDay(e.event_date)} — ${e.n_shooters} shooters`;
```

4. In the date `Link`, replace

```tsx
                    CELL_STYLES[event.has_scores ? 'scored' : 'unscored']
```

with

```tsx
                    CELL_STYLES[cellState(event)]
```

Add to `frontend/src/features/events/explainers.ts`, after `notables`:

```ts
  special: {
    what: 'A special shoot is a Sunday with its own format and number of targets, such as a 60-target 3-bird shoot.',
    read: ["Scores are targets broken out of that shoot's own total, best first. Nobody is ranked or rated."],
    computed: [
      'It counts as a Sunday shot for everyone who came: Sundays shot, streaks and attendance trophies include it.',
      'Its scores stay out of averages, best scores, records, ratings and leaderboards, which are all out of 50.',
    ],
  },
```

Run: `cd frontend && pnpm exec vitest run src/features/events/format.test.ts src/features/events/components/EventList.test.tsx src/features/events/components/SeasonCalendar.test.tsx`
Expected: PASS. (`explainers.test.ts` fails until Step 4 wires `eventExplainers.special` into a component; that is expected here.)

- [ ] **Step 3: Write the failing Sunday-page and results-table tests**

Create `frontend/src/features/events/components/SpecialResultsTable.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import type { EventResult } from '../api';
import { specialDetail } from '../mocks';
import { SpecialResultsTable } from './SpecialResultsTable';

describe('SpecialResultsTable', () => {
  it('lists every shooter best first, out of the shoot’s own total, with no rank or rating', () => {
    renderWithProviders(<SpecialResultsTable results={specialDetail.results} targetTotal={60} />);
    const table = screen.getByRole('table', { name: 'Results' });
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((h) => h.textContent),
    ).toEqual(['Shooter', 'Score (of 60)']);
    const rows = within(table)
      .getAllByRole('row')
      .slice(1)
      .map((r) => within(r).getAllByRole('cell').map((c) => c.textContent));
    expect(rows).toEqual([
      ['Hadley, Ike', '55'],
      ['Kaplan, Noel', '51'],
      ['Kim, Pat', '39'],
    ]);
  });

  it('breaks a tie by name and keeps the round-type filter on profile links', () => {
    const [first, second] = specialDetail.results as [EventResult, EventResult];
    renderWithProviders(
      <SpecialResultsTable
        results={[
          { ...first, display_name: 'Zed, Al', score: 40 },
          { ...second, display_name: 'Ace, Amy', score: 40 },
        ]}
        targetTotal={60}
      />,
      { route: '/events/2026-09-20?rt=sporting' },
    );
    const links = within(screen.getByRole('table', { name: 'Results' })).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(['Ace, Amy', 'Zed, Al']);
    expect(links[0]).toHaveAttribute('href', `/shooters/${second.shooter_id}?rt=sporting`);
  });
});
```

Append inside `describe('EventDetailPage', …)` in `frontend/src/features/events/pages/EventDetailPage.test.tsx` (add `specialDetail` to the import from `../mocks`):

```tsx
  describe('a special Sunday (Plan 17)', () => {
    it('names the shoot and its targets in the header, with no round type', async () => {
      renderEvent(specialDetail);
      expect(
        await screen.findByText('Three Clay Shoot · Special · 60 targets'),
      ).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 1, name: 'Sep 20, 2026' })).toBeInTheDocument();
      expect(screen.queryByText('Sporting')).not.toBeInTheDocument();
    });

    it('explains the counting rule in neutral words', async () => {
      renderEvent(specialDetail);
      const note = await screen.findByRole('note');
      expect(note).toHaveTextContent(/^A special shoot counts as a Sunday shot/);
      expect(note.textContent).not.toMatch(/\b(he|she|his|her)\b/i);
    });

    it('shows shooters, targets and stations, and no median, top score or difficulty', async () => {
      renderEvent(specialDetail);
      const glance = await screen.findByRole('region', { name: 'This Sunday' });
      for (const [label, value] of [
        ['Shooters', '3'],
        ['Targets', '60'],
        ['Stations', '10'],
      ] as const) {
        expect(within(glance).getByText(label).closest('div')?.parentElement).toHaveTextContent(
          value,
        );
      }
      for (const label of ['Median', 'Top score', 'Difficulty', 'Head count']) {
        expect(within(glance).queryByText(label)).not.toBeInTheDocument();
      }
      for (const stat of ['Shooters', 'Targets']) await expectExplainer(glance, `About ${stat}`);
      await expectExplainer(
        screen.getByRole('region', { name: 'Results' }),
        'About special shoots',
        { read: true },
      );
    });

    it('lists the results out of 60, best first, and draws the station grid', async () => {
      renderEvent(specialDetail);
      const results = await screen.findByRole('table', { name: 'Results' });
      expect(within(results).getByRole('columnheader', { name: 'Score (of 60)' })).toBeVisible();
      expect(within(results).queryByRole('columnheader', { name: 'Rank' })).not.toBeInTheDocument();
      expect(within(results).getAllByRole('row')).toHaveLength(4);
      expect(
        await screen.findByRole('img', { name: 'Station hits heatmap for Sep 20, 2026' }, LAZY_CHART),
      ).toBeInTheDocument();
    }, LAZY_TEST_TIMEOUT);

    it('keeps the weather but has no comparison with the previous Sunday', async () => {
      renderEvent(specialDetail);
      await screen.findByRole('table', { name: 'Results' });
      expect(screen.queryByRole('region', { name: 'vs previous Sunday' })).not.toBeInTheDocument();
      expect(screen.getByText('No weather recorded for this Sunday')).toBeInTheDocument();
      // First-timers are told by Sunday insights (Plan 12), which a special Sunday does not get (Decision 12).
      expect(screen.queryByRole('region', { name: 'Notables' })).not.toBeInTheDocument();
      expectUnbrokenOutline();
    });

    it('a special Sunday without a name or a station sheet still reads cleanly', async () => {
      renderEvent({ ...specialDetail, label: null, stations: null });
      expect(await screen.findByText('Special · 60 targets')).toBeInTheDocument();
      const glance = screen.getByRole('region', { name: 'This Sunday' });
      expect(within(glance).getByText('Stations').closest('div')?.parentElement).toHaveTextContent(
        '—',
      );
      expect(screen.queryByText('Station hits')).not.toBeInTheDocument();
    });
  });
```

If `expectExplainer`'s second argument is required in this repo's `test/charts.ts`, pass `undefined` as the other call sites in this file do.

Run: `cd frontend && pnpm exec vitest run src/features/events/components/SpecialResultsTable.test.tsx src/features/events/pages/EventDetailPage.test.tsx`
Expected: FAIL. `SpecialResultsTable` cannot be resolved; the page shows "Sporting", the full five-tile "This Sunday" card, a ranked results table and a "vs previous Sunday" card for the special Sunday.

- [ ] **Step 4: Implement the results table and the special Sunday page**

Create `frontend/src/features/events/components/SpecialResultsTable.tsx`:

```tsx
import { Link } from 'react-router';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import type { EventResult } from '../api';

/**
 * Plan 17 (Decision 20): a special shoot's results as entered, best first. Nobody is ranked or rated
 * there, so the table is the shooter and the score out of the shoot's own total.
 */
export function SpecialResultsTable({
  results,
  targetTotal,
}: {
  results: EventResult[];
  targetTotal: number;
}) {
  // Profile links keep the global round-type filter (C10).
  const href = useRoundTypeHref();
  const sorted = [...results].sort(
    (a, b) =>
      b.score - a.score || a.display_name.localeCompare(b.display_name) || a.ordinal - b.ordinal,
  );
  return (
    <div className="overflow-x-auto">
      <table aria-label="Results" className="w-full text-sm">
        <thead className="text-left text-text-muted">
          <tr>
            <th scope="col" className="py-2 pr-2">
              Shooter
            </th>
            <th scope="col" className="py-2 text-right">
              {`Score (of ${targetTotal})`}
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.round_id} className="border-t border-outline-variant">
              <td className="pr-2">
                <Link
                  to={href(`/shooters/${r.shooter_id}`)}
                  className="inline-flex min-h-11 min-w-11 items-center underline underline-offset-2"
                >
                  {r.display_name}
                </Link>
              </td>
              <td className="py-2 text-right tabular-nums">{r.score}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

In `frontend/src/features/events/pages/EventDetailPage.tsx`:

1. Add the import `import { SpecialResultsTable } from '../components/SpecialResultsTable';` and extend the `../format` import with `isSpecial`, `specialName`, `specialTag`, `targetsOf`.
2. After `attendanceOnlyTitle`, add:

```tsx
/** Decision 20: the counting rule, in neutral words. */
const SPECIAL_NOTE =
  'A special shoot counts as a Sunday shot for everyone who came, so it keeps streaks going. Its scores stay out of averages, best scores, records and leaderboards.';

/** "Three Clay Shoot · Special · 60 targets" (the name is left out when the sheet gave none). */
function specialHeader(event: EventDetail): string {
  const name = specialName(event);
  return `${name === null ? '' : `${name} · `}${specialTag(event)} targets`;
}

function SpecialEvent({ event }: { event: EventDetail }) {
  const stations = event.stations?.layout.length ?? null;
  return (
    <>
      <p role="note" className="rounded-card border border-accent p-3">
        {SPECIAL_NOTE}
      </p>
      <Card title="This Sunday">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          <Stat
            label="Shooters"
            value={String(event.n_shooters)}
            explainer={eventExplainers.shooters}
          />
          <Stat
            label="Targets"
            value={String(targetsOf(event))}
            explainer={eventExplainers.special}
          />
          <Stat label="Stations" value={stations === null ? '—' : String(stations)} />
        </div>
      </Card>
      <Card id="chart-results" title="Results">
        <About explainer={eventExplainers.special} label="About special shoots" />
        <SpecialResultsTable results={event.results} targetTotal={targetsOf(event)} />
      </Card>
      {event.stations !== null && (
        <Suspense
          fallback={
            <Card title="Station hits">
              <Skeleton label="Loading station hits" />
            </Card>
          }
        >
          <StationHeatmap
            stations={event.stations}
            results={event.results}
            date={event.event_date}
          />
        </Suspense>
      )}
    </>
  );
}
```

3. In `EventDetailView`, replace

```tsx
function EventDetailView({ event, sections }: { event: EventDetail; sections: EventSection[] }) {
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-medium">{formatDay(event.event_date)}</h1>
        <p className="text-text-muted">
          <span>{roundTypeLabel(event.round_type)}</span>
          {SOURCE_NOTES[event.round_type_source] ?? ''}
        </p>
      </header>
```

with

```tsx
function EventDetailView({ event, sections }: { event: EventDetail; sections: EventSection[] }) {
  const special = isSpecial(event);
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-medium">{formatDay(event.event_date)}</h1>
        <p className="text-text-muted">
          {special ? (
            <span>{specialHeader(event)}</span>
          ) : (
            <>
              <span>{roundTypeLabel(event.round_type)}</span>
              {SOURCE_NOTES[event.round_type_source] ?? ''}
            </>
          )}
        </p>
      </header>
```

4. Replace

```tsx
          {event.has_scores ? (
            <ScoredEvent event={event} />
          ) : (
            <Notice level={2} title={attendanceOnlyTitle(event.head_count)} />
          )}
```

with

```tsx
          {special ? (
            <SpecialEvent event={event} />
          ) : event.has_scores ? (
            <ScoredEvent event={event} />
          ) : (
            <Notice level={2} title={attendanceOnlyTitle(event.head_count)} />
          )}
```

5. Replace `          {event.has_scores && <VsPrevCard vsPrev={event.vs_prev} />}` with `          {event.has_scores && !special && <VsPrevCard vsPrev={event.vs_prev} />}`.

Run: `cd frontend && pnpm exec vitest run src/features/events`
Expected: PASS, including `explainers.test.ts` (the `special` explainer is now wired, stays under 95 words and never says "event", "class" or he/she) and every existing Sunday-page test.

- [ ] **Step 5: Write the failing profile-card and attendance tests**

Add to `frontend/src/features/shooters/mocks.ts` (import `SpecialRound` from `./api` in its type import):

```ts
/** Plan 17: Hadley's one special shoot (invented name). */
export const hadleySpecials: SpecialRound[] = [
  { round_id: 9001, event_date: '2026-09-20', label: 'Three Clay Shoot', target_total: 60, score: 55 },
];
```

and add to its `handlers`, after the `rounds` handler:

```ts
  http.get('*/api/shooters/:id/special', () => HttpResponse.json([])),
```

Create `frontend/src/features/events/components/SpecialShootsCard.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { expectExplainer } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { hadleySpecials } from '../../shooters/mocks';
import { SpecialShootsCard } from './SpecialShootsCard';

function withSpecials(body: unknown, status = 200) {
  server.use(http.get('*/api/shooters/:id/special', () => HttpResponse.json(body, { status })));
}

describe('SpecialShootsCard', () => {
  it('lists each special shoot newest first, tagged with its targets, linking to the Sunday', async () => {
    withSpecials([
      { round_id: 8001, event_date: '2025-06-15', label: 'Flurry', target_total: 75, score: 61 },
      ...hadleySpecials,
    ]);
    renderWithProviders(<SpecialShootsCard shooterId={3} />, { route: '/shooters/3?rt=sporting' });
    const list = await screen.findByRole('list', { name: 'Special shoots' });
    const items = within(list).getAllByRole('listitem');
    expect(items[0]).toHaveTextContent('Sep 20, 2026');
    expect(items[0]).toHaveTextContent('Three Clay Shoot · Special · 60');
    expect(items[0]).toHaveTextContent('55 of 60');
    expect(items[1]).toHaveTextContent('Flurry · Special · 75');
    expect(within(items[0] as HTMLElement).getByRole('link')).toHaveAttribute(
      'href',
      '/events/2026-09-20?rt=sporting',
    );
    await expectExplainer(
      screen.getByRole('region', { name: 'Special shoots' }),
      'About special shoots',
      { read: true },
    );
  });

  it('says nothing for a shooter with no special shoot, or while it cannot load', async () => {
    withSpecials([]);
    const { container } = renderWithProviders(<SpecialShootsCard shooterId={3} />);
    await new Promise((r) => setTimeout(r, 50));
    expect(container).toBeEmptyDOMElement();
  });

  it('stays silent when the list fails to load', async () => {
    withSpecials({ error: { code: 'x', message: 'nope' } }, 500);
    const { container } = renderWithProviders(<SpecialShootsCard shooterId={3} />);
    await new Promise((r) => setTimeout(r, 50));
    expect(container).toBeEmptyDOMElement();
  });
});
```

Create `frontend/src/features/events/profileSection.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { profileSections } from '../shooters/sections';
import { SpecialShootsCard } from './components/SpecialShootsCard';

describe('the special shoots profile section', () => {
  it('is registered after the weather card and renders its own card', () => {
    expect(profileSections.find((s) => s.id === 'special')).toMatchObject({
      title: 'Special shoots',
      order: 65,
      bare: true,
      Component: SpecialShootsCard,
    });
  });
});
```

Append to `frontend/src/components/charts/builders/sundayCalendar.test.ts`, inside `describe('sundayCalendarOption', …)`:

```ts
  it('draws a special shoot the shooter came to as an accent-ringed cell off the score scale', () => {
    const data: TabularData = {
      ...DATA,
      rows: [...DATA.rows, { date: '2026-09-20', score: null, state: 'special' }],
    };
    const o = sundayCalendarOption(data, OPTS);
    const special = (o.series as HeatmapSeriesOption[])[2] as HeatmapSeriesOption;
    expect(special.name).toBe('Special');
    expect(special.data as Item[]).toEqual([{ value: [2, 8, -3], date: '2026-09-20' }]);
    expect(special.itemStyle).toMatchObject({ color: 'transparent', borderWidth: 3 });
    const label = special.label as { show: boolean; formatter: () => string };
    expect(label.show).toBe(true);
    expect(label.formatter()).toBe('★');
    // The score scale still spans the shot cells only.
    expect((o.visualMap as Record<string, unknown>[])[0]).toMatchObject({ min: 38, max: 44 });
    expect((o.visualMap as Record<string, unknown>[])[2]).toMatchObject({
      seriesIndex: 2,
      show: false,
      min: -4,
      max: -3,
    });
  });

  it('says special shoot in the tooltip', () => {
    const tip = (sundayCalendarOption(DATA, OPTS).tooltip as { formatter: (p: unknown) => string })
      .formatter;
    expect(tip({ seriesName: 'Special', data: { value: [2, 8, -3], date: '2026-09-20' } })).toBe(
      'Sunday 2026-09-20<br/>Special shoot, counts as a Sunday shot',
    );
  });
```

and inside `describe('shotDateOf', …)`:

```ts
  it('opens a clicked special shoot too', () => {
    expect(shotDateOf({ seriesName: 'Special', data: { date: '2026-09-20' } })).toBe('2026-09-20');
  });
```

Append to `frontend/src/features/shooters/charts.test.ts` (add `activeYears`, `attendanceModel`, `monthsModel` to its import from `./charts` if missing, and `hadleyRounds` from `./mocks`):

```ts
describe('special shoots in the attendance views (Plan 17)', () => {
  const held = ['2026-09-06', '2026-09-13', '2026-09-27'];

  it('marks a special shoot as special, never missed, once however many rounds', () => {
    const m = attendanceModel(hadleyRounds, held, 2026, ['2026-09-20', '2026-09-20']);
    expect(m.rows.filter((r) => r.date === '2026-09-20')).toEqual([
      { date: '2026-09-20', state: 'special', score: null },
    ]);
    expect(m.rows.map((r) => r.date)).toEqual([...m.rows.map((r) => r.date)].sort());
  });

  it('never calls a held date missed when the shooter came to a special shoot on it', () => {
    const m = attendanceModel([], ['2026-09-20'], 2026, ['2026-09-20']);
    expect(m.rows).toEqual([{ date: '2026-09-20', state: 'special', score: null }]);
  });

  it('leaves out a special shoot of another year', () => {
    expect(attendanceModel([], [], 2025, ['2026-09-20']).rows).toEqual([]);
  });

  it('counts a special shoot as a year shot and a Sunday shot that month', () => {
    expect(activeYears([], ['2024-06-16'])).toEqual([2024]);
    expect(activeYears(hadleyRounds, ['2024-06-16'])).toEqual([2026, 2024]);
    const months = monthsModel(hadleyRounds, ['2026-09-20']);
    expect(months.rows.find((r) => r.month === '2026-09')).toEqual({ month: '2026-09', sundays: 4 });
    expect(monthsModel([], ['2026-09-20']).rows).toEqual([{ month: '2026-09', sundays: 1 }]);
  });
});
```

Check `hadleyRounds`' September dates before relying on `sundays: 4`: they are 2026-09-06, 2026-09-13 and 2026-09-27 on `origin/feat/special-events` (`ProfileCharts.test.tsx`'s "lists every held Sunday…" expectation lists them). If the base differs, use its count plus one.

In `frontend/src/features/shooters/components/ProfileCharts.test.tsx`:

1. Add `hadleySpecials` to the import from `../mocks`.
2. In the "every empty data set has its own empty state" test (the one asserting `findAllByText('No rounds yet')).toHaveLength(4)`), replace

```tsx
    // Scores over time, the calendar, the distribution and tough days.
    expect(await screen.findAllByText('No rounds yet')).toHaveLength(4);
```

with

```tsx
    // Scores over time, the distribution and tough days; the calendar counts Sundays shot.
    expect(await screen.findAllByText('No rounds yet')).toHaveLength(3);
    expect(screen.getByText('No Sundays shot yet')).toBeInTheDocument();
```

and add `http.get('*/api/shooters/:id/rounds', () => HttpResponse.json([]))` there only if that test does not already override rounds with `[]` (it does on the base; keep it).

3. Append inside `describe('attendance calendar', …)`:

```tsx
    const special = (event_date: string) => ({
      ...eventSummaries[0],
      event_date,
      results_complete: true,
      kind: 'special' as const,
      label: 'Three Clay Shoot',
      target_total: 60,
    });

    async function calendarRows(user: ReturnType<typeof userEvent.setup>) {
      const table = await openTable(user, 'Attendance calendar 2026');
      return within(table)
        .getAllByRole('row')
        .slice(1)
        .map((r) =>
          within(r)
            .getAllByRole('cell')
            .map((c) => c.textContent)
            .slice(0, 2),
        );
    }

    it('shows a special shoot the shooter came to as special, not missed', async () => {
      const user = userEvent.setup();
      server.use(
        http.get('*/api/events', () =>
          HttpResponse.json([...held(['2026-09-13', '2026-09-27']), special('2026-09-20')]),
        ),
        http.get('*/api/shooters/:id/special', () => HttpResponse.json(hadleySpecials)),
      );
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      const rows = await calendarRows(user);
      expect(rows).toContainEqual(['2026-09-20', 'special']);
      expect(rows).not.toContainEqual(['2026-09-20', 'missed']);
    });

    it('never counts a special shoot the shooter skipped as missed', async () => {
      const user = userEvent.setup();
      server.use(
        http.get('*/api/events', () =>
          HttpResponse.json([...held(['2026-09-13']), special('2026-09-20')]),
        ),
      );
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      const rows = await calendarRows(user);
      expect(rows.map(([date]) => date)).not.toContain('2026-09-20');
    });

    it('a shooter with only a special shoot still gets a calendar', async () => {
      const user = userEvent.setup();
      server.use(
        http.get('*/api/shooters/:id/rounds', () => HttpResponse.json([])),
        http.get('*/api/events', () => HttpResponse.json([special('2026-09-20')])),
        http.get('*/api/shooters/:id/special', () => HttpResponse.json(hadleySpecials)),
      );
      renderWithProviders(<ProfileCharts shooterId={340} />, { route: '/shooters/340' });
      expect(await calendarRows(user)).toEqual([['2026-09-20', 'special']]);
      expect(screen.queryByText('No Sundays shot yet')).not.toBeInTheDocument();
    });

    it('counts a special shoot in Sundays shot per month', async () => {
      const user = userEvent.setup();
      server.use(http.get('*/api/shooters/:id/special', () => HttpResponse.json(hadleySpecials)));
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?cal.view=month',
      });
      const table = await openTable(user, 'Sundays shot per month');
      const september = within(table).getByRole('row', { name: /2026-09/ });
      expect(within(september).getAllByRole('cell').map((c) => c.textContent)).toEqual([
        '2026-09',
        '4',
      ]);
    });

    it('opens a clicked special shoot', async () => {
      server.use(
        http.get('*/api/events', () =>
          HttpResponse.json([...held(['2026-09-13']), special('2026-09-20')]),
        ),
        http.get('*/api/shooters/:id/special', () => HttpResponse.json(hadleySpecials)),
      );
      const { router } = renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3',
      });
      const el = await screen.findByRole('img', { name: 'Attendance calendar for 2026' }, LAZY_CHART);
      getInstanceByDom(el)?.trigger('click', {
        seriesName: 'Special',
        data: { date: '2026-09-20' },
      } as never);
      await waitFor(() => expect(router.state.location.pathname).toBe('/events/2026-09-20'));
    });
```

Run: `cd frontend && pnpm exec vitest run src/features/events src/features/shooters src/components/charts/builders/sundayCalendar.test.ts`
Expected: FAIL. `SpecialShootsCard` and `./profileSection` cannot be resolved (the section is not registered); `hadleySpecials`'s type `SpecialRound` is not exported from `./api`; the calendar has no `Special` series and `shotDateOf` returns null for it; `attendanceModel`/`monthsModel`/`activeYears` ignore the special dates; the empty calendar still says "No rounds yet".

- [ ] **Step 6: Implement the hook, the card, the section and the calendar**

In `frontend/src/features/shooters/api.ts`:

1. After `useShooterRounds`, add:

```ts
export type SpecialRound = JsonOf<paths['/api/shooters/{id}/special']['get']>[number];

/**
 * Plan 17: the shooter's special shoots, oldest first. They are appearances only, so they are kept
 * apart from the score charts' rounds. No round-type filter: the endpoint takes none.
 */
export function useShooterSpecials(id: number) {
  return useQuery({
    queryKey: ['/api/shooters/{id}/special', id],
    queryFn: () =>
      unwrap(api.GET('/api/shooters/{id}/special', { params: { path: { id } } })),
  });
}
```

2. Replace

```ts
const heldDates = (events: EventSummary[]) =>
  events.filter((e) => e.results_complete).map((e) => e.event_date);
```

with

```ts
/** A special Sunday is never "missed" (Plan 17 Decision 19): it is drawn from the shooter's own list. */
const heldDates = (events: EventSummary[]) =>
  events.filter((e) => e.results_complete && e.kind !== 'special').map((e) => e.event_date);
```

Create `frontend/src/features/events/components/SpecialShootsCard.tsx`:

```tsx
import { Link } from 'react-router';
import { Card } from '../../../components/ui/Card';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import { useShooterSpecials } from '../../shooters/api';
import { eventExplainers } from '../explainers';
import { formatDay, specialName, specialTag } from '../format';
import { About } from './About';

/**
 * Plan 17 (Decision 19): the shooter's special shoots, newest first, each tagged "Special · 60" with
 * its score out of that total. Renders nothing for a shooter without one (or while it cannot load).
 */
export function SpecialShootsCard({ shooterId }: { shooterId: number }) {
  const query = useShooterSpecials(shooterId);
  // Sunday links keep the global round-type filter (C10).
  const href = useRoundTypeHref();
  if (query.data === undefined || query.data.length === 0) return null;
  const newestFirst = [...query.data].reverse();
  return (
    <Card title="Special shoots">
      <About explainer={eventExplainers.special} label="About special shoots" />
      <ul aria-label="Special shoots" className="flex flex-col divide-y divide-outline-variant">
        {newestFirst.map((s) => {
          const name = specialName(s);
          return (
            <li key={s.round_id}>
              <Link
                to={href(`/events/${s.event_date}`)}
                className="flex min-h-11 flex-wrap items-center justify-between gap-x-3 py-2"
              >
                <span className="font-medium">{formatDay(s.event_date)}</span>
                <span className="text-sm text-text-muted">
                  {`${name === null ? '' : `${name} · `}${specialTag(s)}`}
                </span>
                <span className="tabular-nums">{`${s.score} of ${s.target_total}`}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
```

Create `frontend/src/features/events/profileSection.tsx`:

```tsx
import type { ProfileSection } from '../shooters/sections';
import { SpecialShootsCard } from './components/SpecialShootsCard';

/** C10 profile section (Plan 17): the shooter's special shoots, after the weather card. */
export const profileSection: ProfileSection = {
  id: 'special',
  title: 'Special shoots',
  order: 65,
  bare: true,
  Component: SpecialShootsCard,
};
```

In `frontend/src/components/charts/builders/sundayCalendar.ts`:

1. In `SundayCalendarOpts`, replace the `state` doc comment with `/** 'shot', 'missed' (the club held a shoot and they did not) or 'special' (a special shoot they came to). */`.
2. After `const MISSED = -1;`, add:

```ts
/** A special shoot's value: off the score scale, with its own uncoloured map (Plan 17). */
const SPECIAL = -3;
```

3. In `sundayCalendarOption`, replace

```ts
  const shot: CellItem[] = [];
  const missed: CellItem[] = [];
```

with

```ts
  const shot: CellItem[] = [];
  const missed: CellItem[] = [];
  const special: CellItem[] = [];
```

and replace

```ts
    else if (state === 'missed') missed.push(cell(date, MISSED));
```

with

```ts
    else if (state === 'missed') missed.push(cell(date, MISSED));
    else if (state === 'special') special.push(cell(date, SPECIAL));
```

4. Replace the tooltip's

```ts
        return seriesName === 'Shot'
          ? `${head}<br/>Best score: ${escapeHtml(item.value[2])}`
          : `${head}<br/>Held, not shot`;
```

with

```ts
        if (seriesName === 'Shot') return `${head}<br/>Best score: ${escapeHtml(item.value[2])}`;
        if (seriesName === 'Special') return `${head}<br/>Special shoot, counts as a Sunday shot`;
        return `${head}<br/>Held, not shot`;
```

5. In `visualMap`, after the missed map's closing `},`, add:

```ts
      // A special shoot is not on the 50-target scale: an uncoloured cell under its own map.
      {
        type: 'continuous',
        seriesIndex: 2,
        dimension: 2,
        show: false,
        min: SPECIAL - 1,
        max: SPECIAL,
        inRange: { color: ['transparent', 'transparent'] },
      },
```

6. In `series`, after the `Missed` series, add:

```ts
      {
        type: 'heatmap',
        name: 'Special',
        data: special,
        itemStyle: { color: 'transparent', borderColor: colors.accent, borderWidth: 3 },
        label: { show: true, formatter: () => '★' },
        emphasis: { itemStyle: { borderColor: colors.text, borderWidth: 3 } },
      },
```

7. Replace `shotDateOf` with:

```ts
/** The date of a clicked shot or special-shoot cell, or null for a missed cell or anything else. */
export function shotDateOf(params: { seriesName?: string; data?: unknown }): string | null {
  if (params.seriesName !== 'Shot' && params.seriesName !== 'Special') return null;
  const date = (params.data as { date?: unknown } | undefined)?.date;
  return typeof date === 'string' ? date : null;
}
```

In `frontend/src/features/shooters/charts.ts`:

1. Replace `activeYears` with:

```ts
/** Years with a round or a special shoot (Plan 17), newest first. */
export function activeYears(rounds: ShooterRound[], specialDates: readonly string[] = []): number[] {
  const dates = [...rounds.map((r) => r.event_date), ...specialDates];
  return [...new Set(dates.map((d) => Number(d.slice(0, 4))))].sort((a, b) => b - a);
}
```

2. In `attendanceModel`, change the signature to

```ts
export function attendanceModel(
  rounds: ShooterRound[],
  heldDates: readonly string[],
  year: number,
  /** Plan 17: special shoots the shooter came to; drawn as 'special', never as 'missed'. */
  specialDates: readonly string[] = [],
): ChartModel {
```

and replace

```ts
  for (const date of heldDates) {
    if (date.startsWith(`${year}-`) && !best.has(date)) {
      rows.push({ date, state: 'missed', score: null });
    }
  }
```

with

```ts
  const special = new Set(specialDates);
  for (const date of special) {
    if (date.startsWith(`${year}-`) && !best.has(date)) {
      rows.push({ date, state: 'special', score: null });
    }
  }
  for (const date of heldDates) {
    if (date.startsWith(`${year}-`) && !best.has(date) && !special.has(date)) {
      rows.push({ date, state: 'missed', score: null });
    }
  }
```

3. In `monthsModel`, change the signature to `export function monthsModel(rounds: ShooterRound[], specialDates: readonly string[] = []): ChartModel {` and replace `  const dates = [...new Set(rounds.map((r) => r.event_date))].sort();` with `  const dates = [...new Set([...rounds.map((r) => r.event_date), ...specialDates])].sort();`.

In `frontend/src/features/shooters/components/ProfileCharts.tsx`:

1. Add `useShooterSpecials` to the import from `../api`.
2. In `AttendanceYear`, add a prop `specialDates: readonly string[]` (destructure it and add `specialDates: readonly string[];` to the props type), and:
   - in `fullQuery`, replace `const years = activeYears(rounds).sort((a, b) => a - b);` with `const years = activeYears(rounds, specialDates).sort((a, b) => a - b);`, replace `attendanceModel(rounds, await fetchHeldSundays(queryClient, y, roundTypes), y).rows,` with `attendanceModel(rounds, await fetchHeldSundays(queryClient, y, roundTypes), y, specialDates).rows,`, and add `specialDates` to the `useMemo` dependency list;
   - replace `const m = attendanceModel(rounds, heldDates, year);` with `const m = attendanceModel(rounds, heldDates, year, specialDates);`;
   - replace the subtitle `"Best score on each Sunday you shot; outlined squares are Sundays you missed"` with `"Best score on each Sunday you shot; outlined squares are Sundays you missed; ★ is a special shoot"`.
3. In `AttendanceCalendar`, after `const query = useShooterRounds(shooterId);`, add:

```tsx
  // Plan 17: special shoots count as Sundays shot (an error leaves them out rather than blocking).
  const specials = useShooterSpecials(shooterId);
  const specialDates = useMemo(
    () => (specials.data ?? []).map((s) => s.event_date),
    [specials.data],
  );
```

and replace

```tsx
      waiting={pending}
      isEmpty={(d) => d.length === 0}
      emptyText="No rounds yet"
      controls={viewChips}
```

with

```tsx
      waiting={pending || specials.isPending}
      isEmpty={(d) => d.length === 0 && specialDates.length === 0}
      emptyText="No Sundays shot yet"
      controls={viewChips}
```

then replace `const m = monthsModel(rounds);` with `const m = monthsModel(rounds, specialDates);`, `const years = activeYears(rounds);` with `const years = activeYears(rounds, specialDates);`, and pass `specialDates={specialDates}` to `<AttendanceYear …/>`.

In `frontend/src/features/shooters/explainers.ts`:

- `cal.read`: append `'A ★ square is a special shoot you came to. It counts as a Sunday shot and has no colour, because its score is out of a different total.'`
- `cal.computed`: replace `'Missed = the club has complete results for that Sunday and you have no round in it.'` with `'Missed = the club has complete results for that Sunday and you have no round in it. A special shoot is never missed.'`
- `'cal-month'.computed`: replace `'Each Sunday counts once, however many rounds you shot that day. The round-type filter applies.'` with `'Each Sunday counts once, however many rounds you shot that day, special shoots included. The round-type filter applies.'`

Search for the replaced strings before changing them (`grep -rn "Best score on each Sunday you shot\|Missed = the club has complete\|Each Sunday counts once" frontend/src frontend/e2e`) and update any test or e2e that asserts them in this task (lesson PF-1).

Run: `cd frontend && pnpm exec vitest run src/features/events src/features/shooters src/components/charts`
Expected: PASS, the existing attendance-calendar tests unchanged (the 2026-09-20 in their `held()` list is a regular Sunday there and still reads "missed").

- [ ] **Step 7: Gates, coverage and the affected e2e specs at both viewports**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm exec vitest run --coverage`
Expected: all green; coverage at or above 90% lines and 90% branches.

Then, with the stack from "Running the e2e stack": `pnpm exec playwright test events.spec.ts shooters.spec.ts shooter-charts.spec.ts --project=desktop --project=mobile`
Expected: all pass, the "36 Sundays in 2026" and legend assertions unchanged except for the added "Special shoot" legend entry, which no e2e counts.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/events/format.ts frontend/src/features/events/format.test.ts frontend/src/features/events/explainers.ts frontend/src/features/events/mocks.ts frontend/src/features/events/components/EventList.tsx frontend/src/features/events/components/EventList.test.tsx frontend/src/features/events/components/SeasonCalendar.tsx frontend/src/features/events/components/SeasonCalendar.test.tsx frontend/src/features/events/components/SpecialResultsTable.tsx frontend/src/features/events/components/SpecialResultsTable.test.tsx frontend/src/features/events/components/SpecialShootsCard.tsx frontend/src/features/events/components/SpecialShootsCard.test.tsx frontend/src/features/events/profileSection.tsx frontend/src/features/events/profileSection.test.ts frontend/src/features/events/pages/EventDetailPage.tsx frontend/src/features/events/pages/EventDetailPage.test.tsx frontend/src/features/shooters/api.ts frontend/src/features/shooters/mocks.ts frontend/src/features/shooters/charts.ts frontend/src/features/shooters/charts.test.ts frontend/src/features/shooters/explainers.ts frontend/src/features/shooters/components/ProfileCharts.tsx frontend/src/features/shooters/components/ProfileCharts.test.tsx frontend/src/components/charts/builders/sundayCalendar.ts frontend/src/components/charts/builders/sundayCalendar.test.ts
git commit -m "feat(special): special Sunday in the list, calendar, Sunday page, profile and attendance calendar (Plan 17 T6)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The admin page: import, preview and roll back a special shoot

The upload flow already handles staging, commit, rollback and history. This task gives the special kind its label, its preview card (Decision 22) and its upload hint.

**Files:**
- Modify: `frontend/src/features/admin/format.ts`, `format.test.ts`
- Modify: `frontend/src/features/admin/mocks.ts`
- Modify: `frontend/src/features/admin/components/DiffSummary.tsx`, `DiffSummary.test.tsx`
- Modify: `frontend/src/features/admin/components/UploadForm.tsx`, `UploadForm.test.tsx`
- Modify: `frontend/src/features/admin/components/ImportPreviewView.test.tsx`

**Interfaces:**
- Consumes: Task 1's `SpecialDiff` (via `pnpm gen:api`) and the `SpecialDiff`/`StationsDiff` types pinned in `features/admin/api.ts` (Task 1 Step 12b).
- Produces (Task 8 relies on these strings): kind label `"Special shoot workbook"`; the `Changes` card rows `Sunday`, `Special shoot`, `Targets` (`"60 (10 stations)"`), `Shooters`, `Replaces` (`"—"` or `"Import #12"`); the warning note `"The scores workbook has 3 rows on Sep 20, 2026. …"`; `New names (n)` and `Possible duplicates` as for scores; the hint `"The kind (scores, stations or a special shoot) is detected from the workbook itself."`.

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/features/admin/mocks.ts`, after `stationsPreview`:

```ts
/** Plan 17: a special-shoot workbook's preview (invented names). */
export const specialPreview: ImportPreview = {
  import_id: 6,
  kind: 'special',
  filename: 'special_2026-09-20.xlsx',
  duplicate_of: null,
  findings: [
    {
      code: 'special_total_mismatch',
      severity: 'warning',
      message: 'Total 50 does not match the station hits (51); the hits are used',
      sheet: 'Special Event',
      row: 6,
      event_date: '2026-09-20',
      name: 'Kaplan, Noel',
    },
  ],
  diff: {
    event_date: '2026-09-20',
    label: 'Three Clay Shoot',
    target_total: 60,
    stations: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'],
    n_shooters: 5,
    replaces_import: null,
    regular_rows_on_date: 0,
    new_names: ['Kim, Pat'],
    possible_duplicates: [['Kim, Pat', 'Kimm, Pat']],
  },
  requires_removal_confirmation: false,
};
```

In `frontend/src/features/admin/components/DiffSummary.test.tsx`, add `specialPreview` to the import from `../mocks` and **replace** the placeholder test from Task 1 Step 12a (`'shows an empty Changes card for a special-shoot preview until its view lands (Plan 17 T7)'`) with:

```tsx
  describe('a special-shoot workbook (Plan 17)', () => {
    function row(label: string) {
      return screen.getByText(label, { selector: 'dt' }).nextElementSibling?.textContent;
    }

    it('shows the Sunday, its name, targets and stations, shooters and what it replaces', () => {
      renderWithProviders(<DiffSummary diff={specialPreview.diff} />);
      expect(row('Sunday')).toBe('Sep 20, 2026');
      expect(row('Special shoot')).toBe('Three Clay Shoot');
      expect(row('Targets')).toBe('60 (10 stations)');
      expect(row('Shooters')).toBe('5');
      expect(row('Replaces')).toBe('—');
      expect(screen.queryByRole('note')).not.toBeInTheDocument();
      expect(screen.queryByText('Rows added')).not.toBeInTheDocument();
    });

    it('lists new names and possible duplicates as the scores preview does', () => {
      renderWithProviders(<DiffSummary diff={specialPreview.diff} />);
      expect(screen.getByText('New names (1)')).toBeInTheDocument();
      expect(screen.getByText('Kim, Pat ↔ Kimm, Pat')).toBeInTheDocument();
    });

    it('names the live import it replaces and warns about weekly rows on that Sunday', () => {
      renderWithProviders(
        <DiffSummary
          diff={{ ...specialPreview.diff, replaces_import: 12, regular_rows_on_date: 3 } as never}
        />,
      );
      expect(row('Replaces')).toBe('Import #12');
      expect(screen.getByRole('note')).toHaveTextContent(
        'The scores workbook has 3 rows on Sep 20, 2026. While this special shoot is live they are left out, and rolling it back brings them back.',
      );
    });

    it('says one row in the singular', () => {
      renderWithProviders(
        <DiffSummary diff={{ ...specialPreview.diff, regular_rows_on_date: 1 } as never} />,
      );
      expect(screen.getByRole('note')).toHaveTextContent('has 1 row on Sep 20, 2026.');
    });
  });
```

In `frontend/src/features/admin/format.test.ts`, replace

```ts
    ['stations', 'Station workbook'],
    ['other', 'other'],
```

with

```ts
    ['stations', 'Station workbook'],
    ['special', 'Special shoot workbook'],
    ['other', 'other'],
```

Append inside the top-level `describe` of `frontend/src/features/admin/components/UploadForm.test.tsx`:

```tsx
  it('says the special shoot workbook is detected too, and keeps the input label', () => {
    renderUpload();
    expect(
      screen.getByText('The kind (scores, stations or a special shoot) is detected from the workbook itself.'),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Workbook (.xlsx)')).toBeInTheDocument();
  });
```

Append inside the top-level `describe` of `frontend/src/features/admin/components/ImportPreviewView.test.tsx` (add `specialPreview` to its mocks import; render it the way that file renders `stationsPreview`):

```tsx
  it('previews a special shoot with its kind, findings and Sunday', async () => {
    renderPreview(specialPreview, 'pending');
    expect(
      await screen.findByText('special_2026-09-20.xlsx · Special shoot workbook · Pending'),
    ).toBeInTheDocument();
    expect(screen.getByText(/does not match the station hits/)).toBeInTheDocument();
    expect(screen.getByText('Three Clay Shoot')).toBeInTheDocument();
  });
```

(`renderPreview(preview, status)` is the file's own helper; the header line is `filename · kindLabel(kind) · statusLabel(status)`.)

Run: `cd frontend && pnpm exec vitest run src/features/admin`
Expected: FAIL. `kindLabel('special')` returns `"special"`; the `Changes` card is empty for the special diff; the hint still says "(scores or stations)".

- [ ] **Step 2: Implement**

In `frontend/src/features/admin/format.ts`, replace

```ts
const KIND_LABELS: Record<string, string> = {
  scores: 'Scores workbook',
  stations: 'Station workbook',
};
```

with

```ts
const KIND_LABELS: Record<string, string> = {
  scores: 'Scores workbook',
  stations: 'Station workbook',
  special: 'Special shoot workbook',
};
```

In `frontend/src/features/admin/components/DiffSummary.tsx`:

1. Replace `import type { ImportPreview, ScoresDiff, StationsDiff } from '../api';` with `import type { ImportPreview, ScoresDiff, SpecialDiff, StationsDiff } from '../api';`.
2. Add, after `Removals`:

```tsx
/** New names and possible duplicates, shared by the scores and special-shoot previews. */
function NameHints({
  newNames,
  duplicates,
}: {
  newNames: string[];
  duplicates: ScoresDiff['possible_duplicates'];
}) {
  return (
    <>
      {newNames.length > 0 && (
        <details>
          <summary className="min-h-11 cursor-pointer py-2.5">{`New names (${newNames.length})`}</summary>
          <ul className="flex flex-col">
            {newNames.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </details>
      )}
      {duplicates.length > 0 && (
        <div className="flex flex-col gap-1">
          <h3 className="font-medium">Possible duplicates</h3>
          <ul className="flex flex-col">
            {duplicates.map(([a, b]) => (
              <li key={`${a}|${b}`}>{`${a} ↔ ${b}`}</li>
            ))}
          </ul>
          <p className="text-xs text-text-muted">
            New names are new shooters; merge real duplicates later under Identity.
          </p>
        </div>
      )}
    </>
  );
}
```

3. In `ScoresDiffView`, replace everything from `      {diff.new_names.length > 0 && (` to the end of the possible-duplicates block (the `)}` before `    </div>`) with:

```tsx
      <NameHints newNames={diff.new_names} duplicates={diff.possible_duplicates} />
```

4. Add, after `StationsDiffView`:

```tsx
/** Decision 13: weekly-workbook rows on the special Sunday are left out while it is live. */
function weeklyRowsNote(diff: SpecialDiff): string {
  const rows = diff.regular_rows_on_date === 1 ? '1 row' : `${diff.regular_rows_on_date} rows`;
  return `The scores workbook has ${rows} on ${formatDay(diff.event_date)}. While this special shoot is live they are left out, and rolling it back brings them back.`;
}

function SpecialDiffView({ diff }: { diff: SpecialDiff }) {
  return (
    <div className="flex flex-col gap-3">
      {diff.regular_rows_on_date > 0 && (
        <p role="note" className="rounded-card border-2 border-error-container p-3">
          {weeklyRowsNote(diff)}
        </p>
      )}
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Row label="Sunday" value={formatDay(diff.event_date)} />
        <Row label="Special shoot" value={diff.label} />
        <Row label="Targets" value={`${diff.target_total} (${diff.stations.length} stations)`} />
        <Row label="Shooters" value={String(diff.n_shooters)} />
        <Row
          label="Replaces"
          value={diff.replaces_import === null ? '—' : `Import #${diff.replaces_import}`}
        />
      </dl>
      <NameHints newNames={diff.new_names} duplicates={diff.possible_duplicates} />
    </div>
  );
}
```

5. Replace the Task 1 narrowing

```tsx
      ) : 'events_replaced' in diff ? (
        <StationsDiffView diff={diff} />
      ) : null}
```

with

```tsx
      ) : 'events_replaced' in diff ? (
        <StationsDiffView diff={diff} />
      ) : (
        <SpecialDiffView diff={diff} />
      )}
```

In `frontend/src/features/admin/components/UploadForm.tsx`, replace `        The kind (scores or stations) is detected from the workbook itself.` with `        The kind (scores, stations or a special shoot) is detected from the workbook itself.`

Run: `cd frontend && pnpm exec vitest run src/features/admin`
Expected: PASS, the existing scores and stations preview tests unchanged.

- [ ] **Step 3: Gates and coverage**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm exec vitest run --coverage`
Expected: all green; coverage at or above 90% lines and branches. Then, with the stack from "Running the e2e stack": `pnpm exec playwright test admin.spec.ts --project=desktop --project=mobile` passes (no e2e asserts the old hint; confirm with `grep -rn "scores or stations" e2e`).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/admin/format.ts frontend/src/features/admin/format.test.ts frontend/src/features/admin/mocks.ts frontend/src/features/admin/components/DiffSummary.tsx frontend/src/features/admin/components/DiffSummary.test.tsx frontend/src/features/admin/components/UploadForm.tsx frontend/src/features/admin/components/UploadForm.test.tsx frontend/src/features/admin/components/ImportPreviewView.test.tsx
git commit -m "feat(special): admin preview and copy for special-shoot workbooks (Plan 17 T7)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: End to end at both viewports

One mutating spec covers the whole path against the real stack: upload the special workbook, preview it, commit it, check the Sundays list, the calendar, the Sunday page and the profile at 390×844 and 1440×900, check that the score numbers did not move and the streak did, then roll back. The shared seed is never changed, so the read-only specs and their golden counts stay as they are (Decision 24).

**Files:**
- Create: `frontend/e2e/fixtures/special_2026-09-20.xlsx` (generated by Step 1, invented names only)
- Create: `frontend/e2e/special-events.admin-mutations.spec.ts`

**Interfaces:**
- Consumes: the strings Tasks 6 and 7 produce; `e2e/layout.ts` `whenSettled`, `expectNoSideScroll`; `e2e/fixtures.ts` `test`/`expect` (fails on page errors and CSP violations); `ADMIN_STATE`; `GET /api/shooters?q=`, `GET /api/shooters/{id}` (`odometer.events`, `current_streak`, `rounds`, `clays_thrown`), `GET /api/leaderboards?period=all_time&metric=best_score` (`rows`), `GET /api/events/{date}`.
- Produces: nothing for later tasks.

- [ ] **Step 1: Generate the fixture workbook**

The e2e seed has no Sunday on 2026-09-20. `Hadley, Ike`, `Kaplan, Noel`, `Devlin, Sid` and `Abernathy, Preston` shot 2026-09-13 and 2026-09-27 there; `Kim, Pat` is not in the seed.

```bash
cd backend && uv run python - <<'PY'
import datetime
import openpyxl

ENTRIES = [
    ("Hadley, Ike", [6, 5, 6, 4, 6, 5, 6, 6, 5, 6]),  # 55
    ("Kaplan, Noel", [6, 5, 5, 5, 6, 5, 5, 5, 4, 5]),  # 51
    ("Devlin, Sid", [5, 5, 4, 5, 5, 4, 5, 5, 5, 5]),  # 48
    ("Abernathy, Preston", [4, 5, 4, 5, 4, 4, 5, 4, 5, 4]),  # 44
    ("Kim, Pat", [4, 4, 3, 4, 4, 4, 4, 4, 4, 4]),  # 39, a new shooter
]
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Special Event"
ws.append(["Special event", "Three Clay Shoot"])
ws.append(["Event date", datetime.date(2026, 9, 20)])
ws.append(["Station", *range(1, 11), "Total"])
ws.append(["Targets", *([6] * 10)])
for name, hits in ENTRIES:
    ws.append([name, *hits, sum(hits)])
wb.save("../frontend/e2e/fixtures/special_2026-09-20.xlsx")
PY
uv run python -c "
from sunday_clays.ingest import parse_upload
p = parse_upload(open('../frontend/e2e/fixtures/special_2026-09-20.xlsx','rb').read())
print(p.kind, p.event_date, p.label, p.target_total, [r.total for r in p.rows], [f.code for f in p.findings])
"
```

Expected: `FileKind.SPECIAL 2026-09-20 Three Clay Shoot 60 [55, 51, 48, 44, 39] []`. If `parse_upload`'s name or signature differs on the base, use the dispatcher Task 1's `test_parse_upload_dispatches_and_validates_a_special_workbook` calls.

- [ ] **Step 2: Write the spec**

Create `frontend/e2e/special-events.admin-mutations.spec.ts`:

```ts
import type { Page } from '@playwright/test';
import { ADMIN_STATE } from './authState';
import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

// Project `admin-mutations` (matched by the unanchored /admin-mutations\.spec\.ts/): one worker, after
// every read-only spec. The special Sunday is rolled back in `finally`, so the shared seed and the
// read-only specs' counts never see it. A run that dies between commit and roll back needs `down -v`.
test.use({ storageState: ADMIN_STATE });

const FILE = 'e2e/fixtures/special_2026-09-20.xlsx';
const DATE = '2026-09-20';
const VIEWPORTS = [
  { width: 390, height: 844 },
  { width: 1440, height: 900 },
] as const;
const BEST_SCORES = '/api/leaderboards?period=all_time&metric=best_score';
const SLOW = { timeout: 15_000 };

type Shooter = { shooter_id: number; display_name: string };
type Odometer = { events: number; current_streak: number; rounds: number; clays_thrown: number };
type Board = { rows: { shooter_id: number; value: number; rank: number }[] };

async function apiJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), path).toBe(true);
  return (await response.json()) as T;
}

async function hadleyId(page: Page): Promise<number> {
  const found = await apiJson<Shooter[]>(page, '/api/shooters?q=Hadley');
  const hadley = found.find((s) => s.display_name === 'Hadley, Ike');
  expect(hadley, 'Hadley, Ike in the seed').toBeDefined();
  return (hadley as Shooter).shooter_id;
}

async function odometer(page: Page, id: number): Promise<Odometer> {
  return (await apiJson<{ odometer: Odometer }>(page, `/api/shooters/${id}`)).odometer;
}

async function rollBack(page: Page): Promise<void> {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/admin');
  const row = page
    .getByRole('table', { name: 'Import history' })
    .getByRole('row', { name: /special_2026-09-20\.xlsx/ })
    .first();
  await expect(row).toContainText('Committed');
  await row.getByRole('button', { name: 'Roll back' }).click();
  await row.getByRole('button', { name: 'Confirm roll back' }).click();
  await expect(page.getByText(/^Rolling back #\d+: Done$/)).toBeVisible({ timeout: 120_000 });
  await expect(row).toContainText('Rolled back');
}

test('a special shoot: preview, commit, every page at both sizes, unchanged scores, then roll back', async ({
  page,
}) => {
  test.setTimeout(420_000);
  const id = await hadleyId(page);
  const before = await odometer(page, id);
  const boardBefore = await apiJson<Board>(page, BEST_SCORES);
  expect((await page.request.get(`/api/events/${DATE}`)).status()).toBe(404);

  let committed = false;
  try {
    await page.goto('/admin');
    await page.getByLabel('Workbook (.xlsx)').setInputFiles(FILE);
    await page.getByRole('button', { name: 'Upload and preview' }).click();
    const changes = page.getByRole('region', { name: 'Changes' });
    await expect(changes).toContainText('Three Clay Shoot');
    await expect(changes).toContainText('60 (10 stations)');
    await expect(changes).toContainText('New names (1)');
    await expect(page.getByText('Special shoot workbook').first()).toBeVisible();
    await page.getByRole('button', { name: 'Commit import' }).click();
    committed = true;
    await expect(page.getByText('Rebuilding live data: Done')).toBeVisible({ timeout: 120_000 });

    for (const viewport of VIEWPORTS) {
      await page.setViewportSize(viewport);

      await page.goto('/events?year=2026');
      await expect(
        page.getByRole('list', { name: 'Sundays in 2026' }).getByRole('listitem'),
      ).toHaveCount(37);
      await expect(page.getByText('Three Clay Shoot · Special · 60 · 5 shooters')).toBeVisible();
      await expect(
        page
          .getByRole('region', { name: 'Calendar 2026' })
          .getByRole('link', { name: 'Sep 20, 2026 — Three Clay Shoot, special shoot, 5 shooters' }),
      ).toBeVisible();
      await whenSettled(page);
      await expectNoSideScroll(page);

      await page.goto(`/events/${DATE}`);
      await expect(page.getByText('Three Clay Shoot · Special · 60 targets')).toBeVisible();
      await expect(
        page.getByRole('note').filter({ hasText: 'counts as a Sunday shot' }),
      ).toBeVisible();
      const results = page.getByRole('table', { name: 'Results' });
      await expect(results.getByRole('columnheader', { name: 'Score (of 60)' })).toBeVisible();
      await expect(results.getByRole('row')).toHaveCount(6);
      await expect(results.getByRole('row').nth(1)).toContainText('Hadley, Ike');
      await expect(results.getByRole('row').nth(1)).toContainText('55');
      await expect(page.getByRole('region', { name: 'vs previous Sunday' })).toHaveCount(0);
      await expect(
        page.getByRole('img', { name: 'Station hits heatmap for Sep 20, 2026' }),
      ).toBeVisible(SLOW);
      await whenSettled(page);
      await expectNoSideScroll(page);

      await page.goto(`/shooters/${id}`);
      const card = page.getByRole('region', { name: 'Special shoots' });
      await expect(card).toContainText('Three Clay Shoot · Special · 60', SLOW);
      await expect(card).toContainText('55 of 60');
      await whenSettled(page);
      await expectNoSideScroll(page);
    }

    // Appearance numbers move; score numbers do not (Review Focus 1 and 3).
    const after = await odometer(page, id);
    expect(after.events).toBe(before.events + 1);
    expect(after.current_streak).toBe(before.current_streak + 1);
    expect(after.rounds).toBe(before.rounds);
    expect(after.clays_thrown).toBe(before.clays_thrown);
    expect((await apiJson<Board>(page, BEST_SCORES)).rows).toEqual(boardBefore.rows);
  } finally {
    if (committed) await rollBack(page);
  }

  expect((await page.request.get(`/api/events/${DATE}`)).status()).toBe(404);
  expect(await odometer(page, id)).toEqual(before);
});
```

- [ ] **Step 3: Run it to verify it fails without the feature (RED)**

On the task branch, temporarily revert one visible piece of Task 6, the special branch of `summaryLine` (`git show HEAD:frontend/src/features/events/components/EventList.tsx` is the feature; edit the file locally to delete the `if (isSpecial(e)) { … }` block), rebuild the stack and run:

```bash
E2E_PORT=18080 IMAGE_TAG=task17 docker compose -p task17 -f compose.yaml -f compose.test.yaml up -d --build --wait
cd frontend && E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test special-events.admin-mutations.spec.ts --project=admin-mutations
```

Expected: FAIL at `getByText('Three Clay Shoot · Special · 60 · 5 shooters')`, and the `finally` block still rolls back (the final 404 check is never reached; the history row reads "Rolled back"). Restore the file with `git checkout frontend/src/features/events/components/EventList.tsx` and confirm `git status` is clean apart from the two new files.

- [ ] **Step 4: Run it to verify it passes (GREEN), twice**

```bash
E2E_PORT=18080 IMAGE_TAG=task17 docker compose -p task17 -f compose.yaml -f compose.test.yaml up -d --build --wait
cd frontend && E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test special-events.admin-mutations.spec.ts --project=admin-mutations --repeat-each=2
```

Expected: 2 passed (a rolled-back import is not a duplicate, so the second run uploads again). Then run the whole suite once, `pnpm exec playwright test`, expecting every project green and the read-only counts ("36 Sundays in 2026") untouched, because `admin-mutations` runs after them.

- [ ] **Step 5: Gates and commit**

Run: `cd frontend && pnpm lint && pnpm exec prettier --check .`

```bash
git add frontend/e2e/special-events.admin-mutations.spec.ts frontend/e2e/fixtures/special_2026-09-20.xlsx
git commit -m "test(special): end-to-end special shoot at 390 and 1440 (Plan 17 T8)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9 (operator): Load the real 2026-09-20 sheet, preview first, production on the owner's word

The controller runs this by hand after Task 8 has merged and the owner is previewing `feat/special-events` locally. It has **no branch, no commit and no PR**. The real-name CSV, the converted workbook and every output that shows real names stay outside every repository. Nothing from this task is pasted into a PR, an issue, a commit message or a file under `/Users/bryanmoran/code/sunday-clays-public`.

**Inputs (private, read in place, never copied into a repo):**
- `/Users/bryanmoran/code/sunday-clays/.superpowers/special-events/2026-09-20-three-clay.csv`: 40 rows, header `name,s1,…,s10,total`, names written "First Last".
- `/Users/bryanmoran/code/sunday-clays/.superpowers/special-events/README.md`: the owner's identity rulings. Three sheet spellings map to existing shooters (alias_name rules), and four names are new shooters.

**Working directory:** `WORK=/private/tmp/claude-501/-Users-bryanmoran-code-sunday-clays/3e00affb-d18c-4e87-9d32-23666ed0f18e/scratchpad/special-events` (the session scratchpad, outside every repo). Run `mkdir -p "$WORK"` first.

- [ ] **Step 1: Read the rulings and check that nothing real is tracked**

Read the private `README.md` in full. Write down, in `$WORK/rulings.json` only, the three `{sheet_name, shooter_display_name}` pairs and the four new names, all in "Last, First" order. Then confirm that no repo holds a copy:

```bash
for repo in /Users/bryanmoran/code/sunday-clays-public /Users/bryanmoran/code/sunday-clays; do
  git -C "$repo" ls-files | grep -i -E 'three-clay|special-events/.*\.(csv|xlsx)$' || echo "$repo: clean"
done
git -C /Users/bryanmoran/code/sunday-clays check-ignore -q .superpowers/special-events/2026-09-20-three-clay.csv && echo "csv ignored"
```

Expected: both repos `clean`, and `csv ignored`. If the CSV is not ignored, stop and tell the owner; do not add an ignore rule to the public repo naming the file.

- [ ] **Step 2: Convert the CSV to the special workbook (outside the repo)**

Exactly one name in the CSV is not two words, and the README does not give its "Last, First" form. Before converting, list it in the terminal (never anywhere else):

```bash
python3 -c "
import csv, sys
for r in csv.DictReader(open(sys.argv[1], newline='', encoding='utf-8-sig')):
    if len(r['name'].split()) != 2: print(repr(r['name'].strip()))
" /Users/bryanmoran/code/sunday-clays/.superpowers/special-events/2026-09-20-three-clay.csv
```

Expected: one line. Ask the owner for that person's "Last, First" display name (as the club's records write it, or as it should read if the person is new). Do not work it out yourself. Write the answer only to `$WORK/hand_names.json` as `{"<CSV name, as printed>": "<Last, First>"}`. If the answer makes that person one of the alias rulings or one of the four new names, update `$WORK/rulings.json` to match.

Create `$WORK/convert.py`:

```python
"""Plan 17 Task 9: the 2026-09-20 CSV -> the "Special Event" workbook. Private; never committed."""

import csv
import datetime
import json
import sys
from pathlib import Path

import openpyxl

SRC = Path("/Users/bryanmoran/code/sunday-clays/.superpowers/special-events/2026-09-20-three-clay.csv")
OUT = Path(sys.argv[1])
HAND = json.loads((OUT.parent / "hand_names.json").read_text())  # the owner's answer (Step 2)
STATIONS = [f"s{i}" for i in range(1, 11)]
TARGETS = 6


def last_first(name: str) -> str:
    if name in HAND:
        return HAND[name]
    parts = name.split()
    if len(parts) != 2:
        raise SystemExit(f"row needs the owner's ruling in hand_names.json: {name!r}")
    first, last = parts
    return f"{last}, {first}"


with SRC.open(newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    assert reader.fieldnames == ["name", *STATIONS, "total"], reader.fieldnames
    rows = list(reader)
assert len(rows) == 40, len(rows)

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Special Event"
ws.append(["Special event", "Three Clay Shoot"])
ws.append(["Event date", datetime.date(2026, 9, 20)])
ws.append(["Station", *range(1, 11), "Total"])
ws.append(["Targets", *([TARGETS] * 10)])
seen = set()
for row in rows:
    hits = [int(row[s]) for s in STATIONS]
    assert all(0 <= h <= TARGETS for h in hits), row["name"]
    assert sum(hits) == int(row["total"]), row["name"]
    name = last_first(row["name"].strip())
    assert name not in seen, name
    seen.add(name)
    ws.append([name, *hits, sum(hits)])
wb.save(OUT)
print(f"wrote {OUT}: {len(rows)} shooters, top {max(int(r['total']) for r in rows)} of 60")
```

Run: `cd /Users/bryanmoran/code/sunday-clays-public/backend && uv run python "$WORK/convert.py" "$WORK/three-clay-2026-09-20.xlsx"`
Expected: `wrote …: 40 shooters, top 45 of 60`. A `needs the owner's ruling` exit means a name that is not "First Last" is missing from `$WORK/hand_names.json`: ask the owner for its "Last, First" form, add it there (never to the script or any repo), then re-run.

Then parse it with the app's own parser:

```bash
cd /Users/bryanmoran/code/sunday-clays-public/backend && uv run python -c "
import sys
from sunday_clays.ingest import parse_upload
p = parse_upload(open(sys.argv[1], 'rb').read())
print(p.kind, p.event_date, p.label, p.target_total, len(p.rows), sorted({f.code for f in p.findings}))
" "$WORK/three-clay-2026-09-20.xlsx"
```

Expected: `FileKind.SPECIAL 2026-09-20 Three Clay Shoot 60 40 []`.

- [ ] **Step 3: Work out the three alias keys**

```bash
cd /Users/bryanmoran/code/sunday-clays-public/backend && uv run python -c "
import datetime, json, sys
from sunday_clays.ingest.names import identity_key, name_key
rulings = json.load(open(sys.argv[1]))
for r in rulings['aliases']:
    print(identity_key(name_key(r['sheet_name']), datetime.date(2026, 9, 20)), '->', r['shooter_display_name'])
" "$WORK/rulings.json"
```

Expected: three lines, each a two-word key (no `@2026-09-20` suffix) and the existing shooter it belongs to. Use the "Last, First" sheet spelling the converted workbook carries, not the CSV's "First Last".

- [ ] **Step 4: On the local preview, add the alias rules before staging**

With `PREVIEW` set to the owner's local preview URL and the preview's admin password in `ADMIN_PASSWORD` (from its `secrets/`, never echoed):

```bash
JAR="$WORK/preview.cookies"
curl -sf -c "$JAR" -H 'content-type: application/json' \
  -d "{\"password\": \"$ADMIN_PASSWORD\"}" "$PREVIEW/api/auth/login" >/dev/null
# Look up each target shooter's id (repeat per ruling; q is the surname):
curl -sf -b "$JAR" "$PREVIEW/api/shooters?q=<surname>" | python3 -m json.tool
# Then one rule per ruling:
curl -sf -b "$JAR" -H 'content-type: application/json' \
  -d '{"rule_type": "alias_name", "payload": {"name_key": "<key from Step 3>", "shooter_id": <id>}, "note": "Plan 17: 2026-09-20 special shoot spelling (owner ruling)"}' \
  "$PREVIEW/api/admin/rules"
curl -sf -b "$JAR" "$PREVIEW/api/admin/rules" | python3 -c "import json,sys; print(sum(r['rule_type']=='alias_name' and r['active'] for r in json.load(sys.stdin)))"
```

Expected: each POST returns the new rule; the count rises by exactly 3. Write the three target shooter ids to `$WORK/ruled_ids.json` (a JSON list). Save the full pre-load state for comparison: `curl -sf -b "$JAR" "$PREVIEW/api/leaderboards?period=all_time&metric=best_score" > "$WORK/preview-best-before.json"`, `curl -sf -b "$JAR" "$PREVIEW/api/records?limit=all" > "$WORK/preview-records-before.json"` and `…/api/shooters > "$WORK/preview-shooters-before.json"`.

- [ ] **Step 5: Upload and check the preview before committing**

```bash
curl -sf -b "$JAR" -F "file=@$WORK/three-clay-2026-09-20.xlsx" "$PREVIEW/api/admin/imports" > "$WORK/preview.json"
python3 - "$WORK/preview.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
d = p["diff"]
print(p["kind"], p["import_id"], d["event_date"], d["label"], d["target_total"], d["n_shooters"])
print("new names:", len(d["new_names"]), "replaces:", d["replaces_import"], "weekly rows:", d["regular_rows_on_date"])
print("findings:", sorted({(f["severity"], f["code"]) for f in p["findings"]}))
PY
```

Expected, every line, or stop:
- `special <id> 2026-09-20 Three Clay Shoot 60 40`;
- `new names: 4`, and those four are exactly the README's four new shooters (compare against `rulings.json` by eye in the terminal; do not paste them anywhere);
- `replaces: None` and `weekly rows: 0`;
- no `error` finding and no `special_total_mismatch`. `non_sunday_date` must not appear (2026-09-20 is a Sunday).

If a fifth new name appears, it is a spelling the rulings do not cover: discard the import (`POST /api/admin/imports/<id>/discard`) and ask the owner. Never guess an identity.

- [ ] **Step 6: Commit on the preview and verify**

```bash
curl -sf -b "$JAR" -X POST "$PREVIEW/api/admin/imports/<id>/commit"   # returns {"job_id": …}
curl -sf -b "$JAR" "$PREVIEW/api/admin/jobs/<job_id>"                  # repeat until "status": "done"
curl -sf -b "$JAR" "$PREVIEW/api/events/2026-09-20" | python3 -c "
import json,sys; e=json.load(sys.stdin); print(e['kind'], e['label'], e['target_total'], e['n_shooters'], len(e['results']), max(r['score'] for r in e['results']), e['stations'] is not None)"
```

Expected: `special Three Clay Shoot 60 40 40 45 True`. Then:

- `api/leaderboards?period=all_time&metric=best_score` is byte-for-byte equal to the saved `before` file (`cmp`);
- `api/records` keeps every score section unchanged. `most_events` and `longest_streaks` are meant to change (Task 5), so the records are not compared whole:

```bash
curl -sf -b "$JAR" "$PREVIEW/api/records?limit=all" > "$WORK/preview-records-after.json"
python3 - "$WORK/preview-records-before.json" "$WORK/preview-records-after.json" "$WORK/ruled_ids.json" <<'PY'
import json, sys
before, after, ruled = (json.load(open(p)) for p in sys.argv[1:4])
SCORE = ("highest_scores", "perfect_rounds", "biggest_adjusted", "biggest_jumps", "highest_ratings")
assert after["as_of"] == before["as_of"], "as_of moved"
for key in SCORE:
    assert after[key] == before[key], key
    assert after["totals"].get(key) == before["totals"].get(key), f"totals.{key}"
    assert after["tied_more"].get(key) == before["tied_more"].get(key), f"tied_more.{key}"
def events(body, sid):
    return next((r["value"] for r in body["most_events"] if r["shooter_id"] == sid), 0)
for sid in ruled:
    assert events(after, sid) == events(before, sid) + 1, f"most_events of shooter {sid}"
print("score sections unchanged; the 3 ruled shooters each gained 1 Sunday")
PY
```

  Expected: the last line prints. An `AssertionError` names the section or shooter id that is wrong: stop;
- `api/shooters` has exactly 4 more entries than before, and the three ruled shooters' `/api/shooters/<id>/special` each list the 2026-09-20 shoot;
- open `$PREVIEW/events/2026-09-20` and one ruled shooter's profile at phone and desktop width and confirm that the label, the "Special · 60" tag and the station grid show.

Tell the owner that the preview is loaded, and list the Decision 26 notes to look at. **Stop here until the owner says to go to production.**

- [ ] **Step 7: Production, only after the owner's OK and after `feat/special-events` is on `main` and deployed**

Confirm that the deployed `api` runs migration `0008` (`GET /api/meta` `app_version` matches the merge commit, and `/api/admin/imports` lists without error). Then repeat Steps 4 to 6 against production with the production admin password, through the internal stack on the homelab host or the admin UI. On the Identity page, the rule form for "alias_name" takes the same key and shooter. Use the same `$WORK/three-clay-2026-09-20.xlsx`, and run the same pre-checks (`new names: 4`, no errors, `weekly rows: 0`) and post-checks (the best-score board unchanged, the records' score sections unchanged and the ruled shooters' `most_events` up by 1, 4 new shooters, 40 results on the Sunday page). If a check fails after commit, roll the import back from the admin page (it restores the earlier state exactly, Review Focus 5) and tell the owner.

- [ ] **Step 8: Clean up**

`rm -rf "$WORK"`, which removes the converted workbook, the rulings copy, `hand_names.json`, the cookies and the saved JSON. The source CSV and README stay where the owner keeps them. Report to the owner in plain words: what was loaded, the counts, and that no real name entered any repository.

---

## Self-review (author)

- **Spec coverage.** Data model: Decisions 1–3 and Task 1 (migration 0008, `kind`/`label`/`target_total`). Counting rule: Tasks 3 (seam, streaks, raw SQL), 4 (trophies, insights) and 5 (API, boards, records, club, YIR), each with a no-leak test against the `fx_special` world, as Review Focus 1 lists. UI: Task 6 (list, calendar, Sunday page, "Special · 60" history card, attendance calendar) and Task 7 (admin). Ingest: Tasks 1–2 (staging, preview, versioning, rollback, total verification, alias rules, a weekly-rows flag in both previews). Data handling: Task 9 converts and loads outside the repo, preview first and production on the owner's word. Process rules: RED/GREEN steps throughout, the 90% gates in every task, an expand-only migration with a documented rollback limit, goldens untouched (the shared fixtures never gain a special Sunday), and e2e at both viewports (Task 8).
- **Deliberate gaps, flagged for the owner (Decision 26):** the Decision 8 list stays on regular Sundays; CSV upload is an operator conversion rather than a second upload format; a special Sunday has no Sunday-page insights and so shows no first-timers; `last_score_date` would anchor on a special Sunday if one were ever the latest.
- **Cross-task contracts checked.** Task 1's widened `ImportPreview.diff` would break the frontend typecheck on its own PR, so Task 1 Step 12a pins `StationsDiff`/`SpecialDiff` in `features/admin/api.ts` with a placeholder branch that Task 7 replaces. Task 5's new payload fields carry defaults, so they are optional in the generated TS (checked against `since?`/`window_stats?` in today's `schema.d.ts`) and existing mocks stay valid. `useShooterSpecials` lives in `features/shooters/api.ts` and its default MSW handler in `shooters/mocks.ts`, so every profile render has a handler. Task 6's mocks keep the special Sunday out of `eventSummaries`, whose counts other tests assert.
- **Names.** Every fixture, mock and e2e name is invented (`Hadley, Ike`, `Kaplan, Noel`, `Devlin, Sid`, `Abernathy, Preston`, `Kim, Pat`, plus `Ace, Amy`, `Zed, Al`, `Flurry`). The real rulings are referenced by path only, and Task 9 keeps every real-name artefact in the session scratchpad and deletes it at the end.
- **Known risks for reviewers.** The `fx_special` world adds one fixture build per backend run (Decision 23). The e2e spec mutates the shared stack and relies on `finally` to roll back, as the existing stations-variant spec does. Task 6's `ProfileCharts` month-view assertion depends on `hadleyRounds` having three September Sundays (the step says how to adjust).
