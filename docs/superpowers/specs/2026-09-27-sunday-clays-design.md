# Sunday Clays — Design Spec

> Date: 2026-09-27 · Status: approved · Implementation plan: `docs/superpowers/plans/2026-09-27-00-master.md`

## Context
The Sunday Clays group (Sundays 10am–12pm, Tri-County Gun Club, Tualatin/Sherwood OR) tracks scores in two Excel
workbooks. The repo `gitgat/sunday-clays` is empty except for those two files. Goal: a web app at
**sundayclays.claysmasher.com** that ingests new versions of the workbooks, keeps a versioned, rollback-able
database, and gives members a modern, explorable analytics experience (per-shooter, per-station, weather,
calendar, trends, leaderboards with a time machine, achievements) on both mobile and desktop.

The implementation plan lives in `docs/superpowers/plans/2026-09-27-00-master.md`: the spec spans ~10 subsystems, so
it decomposes into 11 sub-plans that share one binding **Architecture Contract**; each sub-plan yields working,
tested software on its own and is executed by parallel Opus subagents as GitHub stacked PRs gated by CI.

## 1. Source data (verified by inspection 2026-09-27)

### `02 Scores and Attendance History.xlsx` — cumulative, authoritative
- **ALL SCORE DETAIL** (7,480 rows): `Name` ("Last, First"), `Score Shot` (int 0–50; every round is 50 targets),
  `Event` (date, always Sunday), `Status` (Member/Guest/Deceased, recorded per row: Member/Guest can change between
  a shooter's rounds, e.g. 9 shooters have both; Deceased is written on every row of a deceased shooter's history), `Class` (sparse gauge:
  12 Gauge, Sub-Gauge, SxS, 28/20 Gauge; "29 Gauge" (1 row) → "28 Gauge" + flag (user: a 28ga typo); unknown values kept + flagged; whitespace→null). 311 events 2020-01-05 →
  2026-09-27; 7–52 rows/event; rows sorted by score desc.
- **Multi-round days**: 9 dates where some shooters have 2 rows. Round order/type is not recorded.
- **Name hygiene**: trailing spaces/NBSP, missing comma ("Linwood Luther"), typos (Preutt/Pruett, Hamond/Hammond,
  Farbanks/Fairbanks, Roland/Brett, Lindenmeb/Lindenmeyer, Wendell/Grant W, Dave/David), first-name-only guests
  (2025-02-23), markers like "Amos**", "Barrett (Raymond's Dad)".
- **Score Frequency**: derived — ignore.
- **Attendance History**: `Date, Count, Median`. 360 dated counts from 2018-12-30 (43 pre-2020 events have
  attendance only; 6 later dates have attendance but no scores; 29 dates count ≠ score rows). Future dates
  pre-filled to 2029 with no count → ignore rows with empty Count.

### `05 Station Scores.xlsx` — ROLLING (older tabs deleted; old data is gone)
- One tab per event named "M D YY". A2 = event date; row 4 = station numbers (currently 4..10); row 5 = target
  count per station (7,7,7,7,7,7,8 = 50); row 7 = median formulas; row 9 header; rows 10+ = Name, hits per
  station, SUM total, col J rank. Parse by locating labels ("STATION #", "TARGET COUNT", "Name"), not fixed cells.
- `Name List (2)` = roster (ignore except as optional name hints).
- Known discrepancy: 9/13 Hadley, Ike station sum 36 vs scores file 34 → must be flagged.

### Domain rules (from user)
- **Round type** (two values only; owner decision 2026-09-29): if any station that day has an odd target count ⇒ **Super Sporting**, else **Sporting** — including Sundays with no station data. An admin override wins.
  No station data ⇒ **Unknown** (admin override allowed).
- **Station numbers are fixed physical spots**; presentations change on resets → admins log reset dates to
  split difficulty into "eras".
- **Unknown names default to new shooters** (people come and go). Fuzzy near-matches get a non-blocking
  "possible duplicate?" hint; merge any time later.
- **Deceased**: full history + memorial marker (profile, Plan 08 T2a); never excluded because of status. They appear
  on all-time avg/best/wins/events/rounds boards and Records, and on rating boards at time-machine dates when
  they were active.

## 2. Ingest, versioning, rollback
- Every upload = immutable **import** (raw file bytes + sha256 + kind + parsed rows + status).
  File kind detected by sheet structure, not filename. Duplicate sha256 → "already imported" notice.
- Flow: **parse → validate → preview diff vs live** (events added/removed, rows added/changed/removed, new
  shooters, possible duplicates, station-vs-score mismatches, non-Sunday dates, 3+ rounds/day, out-of-range
  values) → **commit**.
- **Live data is rebuilt, never patched**: latest committed scores import + union of all committed station
  imports (newest import wins per event date; the parser drops empty and ambiguous duplicate-date sheets, so they never override) + active overlay rules → live tables → analytics recompute.
  7.5k rows ⇒ full rebuild in seconds, run as a worker job.
- **Rollback**: mark import `rolled_back` → rebuild. Station events revert to prior import's version or vanish.
- **Overlay rules** (durable, versioned, toggleable, audited): alias/merge shooter, rename display name, score
  override, round-type override, hide row, station reset note, deceased/status override.
- Station rows link to a round by (event, shooter); on multi-round days pick the round whose score equals the
  station total, else pair with a remaining round and flag; a round is never linked twice (C5 `link_station_entries`).
- First-name-only names are event-scoped: each such appearance is a new shooter by default, and admins merge them.

## 3. Data model (Postgres)
- Staging: `imports`, `import_score_rows`, `import_attendance_rows`, `import_station_sheets`,
  `import_station_layout`, `import_station_hits`.
- Identity & rules: `shooters`, `shooter_aliases` (normalized name → shooter), `rules` (type, payload jsonb,
  active, created_at, role), `audit_log`.
- Live (rebuilt): `events` (date, round_type + source, attendance_count, n_rounds, n_shooters),
  `rounds` (event, shooter, score, gauge_class, status), `station_layouts`, `station_hits`.
- Weather: `weather_hourly` (date, hour, raw fields), `event_weather` (10–12 aggregate + condition label),
  `forecast_cache`.
- Analytics (recomputed): `round_metrics` (field-adjusted, expected, residual, percentile, rank, rating before/
  after), `rating_history` (shooter, event, mu, sigma), `event_metrics` (difficulty, median, spread),
  `achievements_awarded` (shooter, code, event, round), `jobs` (Postgres-backed queue).

## 4. Analytics
**Ground rules**: multi-round days → all rounds count toward averages/totals; event rank uses best round.
Round type is a global filter (the only one; status and gauge filter only leaderboards and the Explorer). With today's
data 309 of 311 scored events are `sporting` by default (2 are `super_sporting`), so the filter is only as sharp as the station imports and overrides behind it. Leaderboards have min-round thresholds. Every metric is time-sliceable
(as-of date) to power the time machine.

**Skill model** (`analytics/skill.py`, pure + tested): score = skill(shooter, t) + difficulty(event) + noise.
Skill evolves as a random walk (per-shooter Kalman filter); online filter; per-event difficulty from leave-one-out
precision-weighted residuals, published centered on the trailing-year level; difficulty absorbs round type; an
explicit round-type offset is deferred until ≥20 events have a station-backed round type of each kind. Outputs per event: rating μ/σ snapshot,
day difficulty, expected score, residual (over/under-performance), next-Sunday predictions + win odds.

**Shooter profile**: rounds/events/first/last, PBs (overall, by year/month/season/weather/round type/gauge),
avg/median, rolling form, floor/ceiling/bad-day rate, wins/podiums/avg percentile, rating curve with band &
peak, learning curve vs club, rust effect after layoffs, attendance calendar + streaks, weather sensitivity
(shrunk toward club), station strengths/"where you lose targets", auto rivals + nemesis + head-to-head,
compare 2–4 shooters, milestone projections, "That's me" personalization (localStorage).

**Club**: attendance 2018→ (count vs rows), YoY, unique shooters/yr, core regulars, newcomer cohorts &
retention, lapsed regulars, guest→member conversion, score distribution by year (ridgeline), top-score trend,
parity, difficulty series, turnout vs weather, seasonality, "On this day", Year in Review (club + shooter).

**Event page**: results + ranks, round type, weather card, station heatmap (shooter × station), difficulty,
rating changes, notables (PBs, first-timers, streaks, milestones), vs previous Sunday, share image.

**Stations**: hit % per station with CI (target-count normalized), per era, separator stations, clean rate,
per-station leaders, wind × station (once n is sufficient — show sample size).

**Weather**: Open-Meteo archive (hourly, America/Los_Angeles, event window 10:00–12:00) at club coordinates (configurable;
default 45.3525, -122.8082, verified for 13050 SW Tonquin Rd, Sherwood OR 97140): temp, apparent temp, precip, wind
speed/gust/direction, cloud cover, humidity, pressure. Conditions explorer (sliders), scatter + regression, wind-rose
by score, sensitivity leaderboard, next-Sunday forecast card with predicted field median and per-shooter expectation.

**Leaderboards & time machine**: season / rolling-12 / all-time × avg, best, wins, attendance, most improved,
rating; filters round type, gauge, member/guest; season championship points;
date slider "as of", bar-chart race, bump chart; Records page.

**Achievements & Trophy Case** (dated, rarity %). Mostly **non-ranking** — earned by showing up and shooting, not
by beating others. Each achievement is a *trophy* with its own small illustrated icon; tiered families award
bronze → silver → gold → platinum → diamond trophies and show **progress to the next tier** ("1,742 / 2,500 clays
broken").
- *Milestone families (tiered)*: Clays Broken (lifetime sum of scores) 100/500/1,000/2,500/5,000/10,000;
  Clays Thrown (rounds × 50) 500/1,000/2,500/5,000/10,000; Events Attended 1/10/25/50/100/150/200/250;
  Years Active (distinct calendar years) 2/3/5/7; Big Year (events in one calendar year) 20/30/40;
  Iron Streak (consecutive held events) 4/8/12/26; Round Score (best single round) 30/35/40/45/48/50;
  Station Cleaner (stations cleaned) 1/5/10/25; Personal Bests set 1/5/10.
- *One-off trophies*: Doubleheader, New Year's shooter, Anniversary (1 yr, 5 yr), Welcome Back (returned after
  ≥180 days away), Joined the Club (guest → member), Both Disciplines (shot sporting and super sporting),
  Four Seasons (winter/spring/summer/fall in one year), Perfect Month, Sub-Gauge, Rain / Cold / Heat / Wind
  shooter, All-Weather (all four), Mudder (40+ in rain), Comeback (+15), Above Average ×3.
- *Competition trophies (the only ranking-based ones)*: First Win, Podium, Station Top
  Gun, Hardest-Station Clean.
- **Lifetime "odometer"** on every profile (non-ranking): clays thrown, clays broken, hit %, rounds, events,
  years active, current/longest streak, favorite month, trophies earned.
- Surfaces: Trophy Case on the profile (earned trophies in metal colors, locked ones greyed with progress bars),
  a club Trophy Room (every trophy, holder count, rarity, recent unlocks), "Trophies earned today" on event
  pages, and "Your next trophy" on the home "me" panel.
Defined declaratively (family, tiers, value function or evaluator) and evaluated during rebuild; unit-tested each.
- **Trophy art** is generated with the user's running **imagen** instance (`../imagen`; external deployment
  `https://imagen.thehalf.io`, session login, `POST /api/generations` with `Idempotency-Key`, poll
  `GET /api/generations/{id}`, download `GET /api/assets/{id}/bytes`). A dev-only tool in this repo submits one job
  per trophy/tier (several seeds each), builds a contact sheet for the user to pick favorites, then post-processes
  picks (circular medallion mask, 256 px + 128 px WebP) into committed static assets. The app never calls imagen at
  runtime; until art exists the UI renders a generic SVG trophy tinted with the tier's metal color.

**Explorer**: metric × group-by (shooter, month, year, season, weather band, round type, station) × filters ×
date range → chart + table + CSV + shareable URL. One backend query endpoint with a validated JSON query spec
(also the future AI target).

## 5. UX & visual design
- **Mobile and desktop both first-class**: desktop = sidebar nav + multi-column dashboards; mobile = bottom tab
  bar, stacked cards, swipe/zoom charts. Playwright runs both viewports.
- **ClaySmasher defaultBrand theme** (source `../claysmasher/lib/core/theme/`): surface #1A4D2E, elevated
  #2D5F3F, primary #9E5530, primary container #C76D3F, accent #E8A77A, text #FEFBF6, secondary text #D4E7DD,
  outline #D1E7DA / #4A7C59, error #FEE2E2 / #DC2626. Roboto. Radii: cards 12, buttons 20, sheets 16.
  Implemented as Tailwind theme tokens + an ECharts theme.
- **Metabase-like charts**: Apache ECharts. Every data chart sits in a reusable `ChartFrame` (tooltips, table view,
  CSV, fullscreen, brush/pinch zoom on cartesian charts); `ChartCard` = `ChartFrame` + explore controls
  (metric/group-by/filter chips, chart-type switch, click-to-drill). All state in URL.

## 6. Architecture & infra
- **Backend**: Python 3.13, FastAPI, SQLAlchemy 2 + Alembic, Pydantic v2, openpyxl, pandas/numpy (+ scipy),
  httpx. Packages: `ingest/` (pure parsers), `domain/` (rebuild + rules), `analytics/` (pure fns),
  `weather/`, `explorer/`, `api/`, `worker/`. uv for deps.
- **Frontend**: React + Vite + TypeScript, TanStack Query, React Router, Tailwind, ECharts. Share images rendered
  client-side (html-to-image → PNG → Web Share API / download). Rationale: the site is password-protected, so
  link-preview crawlers can't fetch server-rendered OG images anyway; client-side is simpler and testable.
- **Auth**: two passwords (viewer, admin) from Docker secrets, argon2-hashed compare → signed httpOnly session
  cookie with role; login rate limit; admin actions audited.
- **Compose** (`compose.yaml`, Swarm-ready: env/secrets only, named volumes, healthchecks, no host binds):
  `caddy` (static SPA + `/api` proxy on plain `:80`; in the Swarm, TLS terminates at the existing **Traefik**
  (`traefik_public` network, `websecure` entrypoint, `cloudflare` certresolver — same pattern as
  `../imagen/swarm-config/imagen/docker-compose.yml`); locally Caddy serves `:8080`), `api`, `worker` (Postgres job queue;
  scheduled forecast refresh + weather sync), `db` (Postgres 17), `backup` (verified nightly pg_dump + restore script).
- The DB, including `imports.file_bytes`, rules and aliases, is the system of record for station history, because the
  station workbook is rolling. Swarm data lives on `/var/data/sundayclays/*` inside the fleet restic backup.
- Images built in CI and pushed to GHCR (`ghcr.io/gitgat/sunday-clays-*`) only after `ci-ok` passes.

## 7. Engineering process
- **CI first** (GitHub Actions) before any feature code: ruff + mypy --strict, eslint + tsc + prettier, pytest
  (real Postgres service), vitest, coverage gate **≥90%** backend and frontend separately, Docker builds,
  Playwright e2e against the compose stack (mobile + desktop viewports).
- **Ratchets**: coverage baselines in `ratchets/baseline.json` and absolute bundle budgets in `ratchets/budgets.json`.
  CI fails on regression. Task PRs never edit `ratchets/`; after each wave the controller raises the baselines in one
  `chore/ratchet-wave-<N>` PR. Lint warnings are held at 0 (`ruff check`, `eslint --max-warnings 0`).
- **Branch protection** on `main`: requires the aggregate `ci-ok` check, which fails if any CI job fails, is cancelled
  or is skipped; strict up-to-date branches, linear history, no force-push or deletion, admins included, no review
  requirement. Merge queues are org-only (this is a personal-account private repo) and are not used.
- **Lefthook** pre-commit (lint/format) + pre-push (tests), mirroring claysmasher.
- **TDD** everywhere; real workbooks as golden fixtures with snapshot tests of parsed output & rebuild.
- **Subagent-driven, parallel**: one plan task = one branch/worktree = one PR; the controller merges PRs one at a
  time once `ci-ok` is green on an up-to-date branch.
- No Claude code-review workflow (user will set up separately).

## 8. Phasing
Phase 1 = everything in §1–§7 of this spec, delivered by the 11 sub-plans of the master plan. **Phase 2 (AI, deferred, not
planned here)**: NL "ask the stats" → validated Explorer QuerySpec; weekly recaps; coaching insights; ingest
layout/name assistant; YIR narratives — grounded on computed facts only, cached, feature-flagged.
