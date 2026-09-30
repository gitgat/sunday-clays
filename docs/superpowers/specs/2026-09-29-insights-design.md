# Sunday Clays: Insights — Design Spec

> Date: 2026-09-29 · Status: revised after critique (resolution in §8) and the owner's answers (D10–D12, §7) · Parent spec: `2026-09-27-sunday-clays-design.md` · Contract: master plan C1–C12
> Sources: `.superpowers/sdd/insights/CATALOG.md` (§0 data facts, §2/§6.2 spot-checks, §3 architecture notes, §4 shortlist, §5 kudos, §6 round 2, §7 decisions) and `.superpowers/sdd/explainers/STYLE.md`.

An **insight** is one short, plain-language sentence about a shooter, a Sunday, the club, the season or a station, computed from the data, backed by a chart that proves it, and explained in plain arithmetic. A **kind** is one generator (for example `pf.pb`); one kind can show on several pages.

---

## 1. Goal and user decisions

**Goal.** Give every page a few true, specific and friendly things to notice, with lots of variety, including kudos for people who keep improving, without asking anyone to read a chart first.

**Binding user decisions (2026-09-29)**

| # | Decision | Where it is enforced |
|---|---|---|
| D1 | Named shooters get positive or neutral text only ("always positive, can call out people"). Club- or field-level negatives are fine. | §4.1 (by construction, per-clause polarity §3.3, DB CHECK, tests) |
| D2 | Neutral pronouns only: never he/she/his/her/him/hers/himself/herself. Use the name, they/their, or you. | §3.5, §4.2 |
| D3 | No "class" wording. The rating-based A/B/C/D classes are being removed from the app, so every class-based kind is dropped (§2.4). | §2.4, §4.2 (banned word) |
| D4 | Every insight has a chart link that proves it and a plain-language "How we worked it out". | §3.6, §3.8, proof test §5 |
| D5 | Insights are static until a new upload lands: they are computed in a recompute step, never on request. | §3.2 |
| D6 | "A lot of options", including kudos and improvement streaks. | §2 (74 v1 kinds, 147 later), kudos strip §3.8 |
| D7 | Only Sundays exist: say "Sunday", never "event". | §4.2 (banned word) |
| D8 | Charts default to a recent window (last 3 months) and every chart has an explainer. The chart link sets the window that makes the evidence visible. | §3.6 |
| D9 | Good vibes only, golf-style: a shooter is compared with their own history or the whole field, never with another named person. No rivals, head-to-head, upsets, giant-killer or win odds. Overall standings (wins, podiums, season points, rankings) are fine, but a named clause never places one named shooter ahead of or behind another. | §2.2 samples, §2.3 note, §2.4, §4.1, §4.2 (D9 lint) |
| D10 | Kudos strip: at most 10 chips, then an "and N more" chip that opens the full list. | §3.4, §3.7, §3.8, §5 |
| D11 | Every logged-in viewer sees every profile's insights, including `pf.digest-line`. Only the `_you` wording is limited to the viewer's own ("Me") profile. | §3.4, §3.5 |
| D12 | The Plan 08 profile card stats (floor/ceiling, bad-day rate, form hot/cold, rust "after 3+ weeks off" on a 28-day gap, plus the rest of that card) **stay** as neutral profile stats: they describe one shooter and are not person-vs-person. The card and `GET /api/shooters/{id}/insights` are kept; the insights section sits beside them without repeating a card fact. | §2.4, §3.4 (stats-card overlap), §3.7, §3.9, §6 |

---

## 2. Scope

### 2.1 Terms used in the tables

| Term | Meaning (plain arithmetic) | Source column |
|---|---|---|
| Sunday | A held Sunday: results complete (C4 `results_complete`). Attendance-only Sundays count only for attendance kinds. | `events` |
| Round | The shooter's best round of that Sunday (`is_best_round`), unless a row says otherwise. 39 of 7,319 rounds are second rounds, so this rarely matters. | `rounds` |
| Field's middle score | The median score of everyone who shot that Sunday. | `field_median` |
| Vs the field | Score minus the field's middle score. | `adjusted` |
| Usual for a day like this | The skill model's expected score for that shooter on that Sunday. | `expected`; gap = `residual` |
| Skill rating | The model's estimate of current skill, in targets (top ≈ 44.9). | `rating_history.mu` (published scale) |
| How the day played | Skill-adjusted day difficulty; positive = tougher than a typical recent Sunday. | `event_metrics.difficulty` |
| Prior | Strictly before the anchor Sunday S. | — |
| Active | ≥ 5 rounds ever and ≥ 1 in the last 364 days (C7), judged as of the anchor Sunday S (evergreen kinds: the latest held Sunday), not today, so a quoted count can differ from the directory's `?active=` count on a non-Sunday. 84 shooters on 2026-09-27. A kind that quotes a population and links a chart uses the same population in both (§3.6). | `shooter_profiles` |
| Wet / dry, bands | C7 single-definition bands: wet ≥ 0.02 in; temp `<40, 40–55, 55–70, 70–85, ≥85` °F; gust `<10, 10–20, ≥20` mph. | `frames.*_band` |
| Own tier T | The highest of 45 / 40 / 35 that the shooter has reached on 10–60% of their last 52 rounds (35 only if their usual is ≤ 39). | derived |
| Shuffle test p% | Shuffle the wet/dry (or band) labels among the shooter's own rounds 1,000 times with seed `hash(kind, shooter_id)`; the real gap must beat p% of shuffles. | derived |
| Sundays shot | `shooter_profiles.n_events`: Sundays with at least one round. There is no per-shooter attendance before 2020 (the 2018–19 attendance rows are head counts only). | `shooter_profiles` |
| Left-censored | C4 `left_censored`: first round within 56 days of the earliest data, so the true first Sunday is unknown. Such shooters get no "first Sunday" or anniversary claims (same rule as `event_notables`). | `shooter_profiles` |
| Rate | Spot-check result (CATALOG §2, §6.2): profile kinds as "active shooters of 84 who see it now", Sunday kinds as "% of the last 145 Sundays it fires". "prov." = guard not yet spot-checked; tuned in the build phase to the target rate shown. | — |

**Page codes:** P profile · S Sunday page (`/events/:date`) · H home · C club · L leaderboards · R records · St stations.
**Rank basis:** `care` (1–5, editorial weight) and `strength` (effect ÷ guard threshold). Every variant's strength is defined so it is ≥ 1 at its own guard; where a variant's guard is not the headline threshold the table gives it a fixed value. Production clamps to ≥ 1 with a logged warning and never raises (§3.3). Full formula in §3.4.
**Chart codes:** `Ex` = Explorer link written as `metric/agg/group_by | filters`, plus `hl`, `ref`, `cmp` and the window `[from, to]`. `Pg` = page chart anchor `route#urlKey` plus `hl`; every anchor is in the anchor registry (§3.6.4). Every link carries an explicit window and "all round types" (§3.6.1); where a row gives no window it is all-time, written as [first held Sunday, S]. Charts marked **new** are listed in §3.6.3.
**Families and home slots** for every kind are in §2.2.8.
**Sample names are placeholders.** Every sample is written in the third person with a name; on the viewer's own profile (the "Me" shooter, `lib/me.ts`) the `you` variant renders instead (§3.5).

### 2.2 v1 kinds (74)

Family tags drive the variety rules (§3.4): `form`, `streak`, `milestone`, `race`, `record`, `weather`, `turnout`, `newcomer`, `station`, `trophy`, `recap`. **K** marks a kudos kind (feeds the kudos strip).

#### 2.2.1 Shooter subject: form and improvement (18)

| id | pages | sample text | trigger / computation | guard | rank basis | chart link |
|---|---|---|---|---|---|---|
| `pf.pb` **K** | P S H | "New personal best for Pat K.: 46, beating the 44 from Aug 2024." Sunday roll-up: "Personal bests today: Pat K. 46, Sam R. 41." | score at S > max of all prior scores, using the shared C12 `personal_bests` helper so Notables, trophies and insights agree | S/H: the C12 rule (≥ 5 prior rounds, strictly above the old best); roll-up ≤ 5 names. P: a separate evergreen row (variant `profile`, §3.1) for the latest PB if set in the last 52 Sundays. Rate re-measured in Phase 1d (29% of Sundays / 23/84 at the old ≥ 12 prior) | care 5; strength = 1 + (new − old)/2 | Pg `/shooters/{id}#trend`, `hl=S`, PB line; window [S − 3 mo, S] |
| `pf.tied-best` **K** | P S H | "Pat K. matched a personal best of 44, first set in Aug 2024." | score at S = prior max | ≥ 12 prior; old best ≥ usual + 3. 26% | care 4; strength = (best − usual)/3 | Pg `#trend`, `hl=first,S`, PB line; window [first − 1 mo, S] |
| `pf.season-best` | P | "Best round of 2026 so far for Pat K.: 41 on Aug 3." | max score this calendar year, set at S, not a PB | set in the last 8 Sundays; ≥ 5 rounds this year; best ≥ this year's own average + 3. 1/84 (fallback) | care 2; strength = gap/3 | Pg `#trend`, `hl=S`; window [Jan 1, latest] |
| `pf.first-tier` **K** | P S | "Casey L. broke 40 for the first time." | first round ever ≥ L, level L ∈ {40, 45, 48} | ≥ 10 prior rounds. 13% | care 4; strength by level (40: 1, 45: 1.5, 48: 2) | Ex `score/max/event \| sh=id`, `ref=L`, `hl=S`; window [first round, S] |
| `pf.first-since` **K** | P S H | "First 45 since June 2024 for Pat K." | at S, reached a level (win, podium, 45+, 40+) last reached ≥ 365 days and ≥ 15 rounds earlier | level reached ≥ 2 times before. 10% | care 4; strength = days away / 365 | Pg `#trend`, `hl=last,S`, `ref=tier`; window [last − 1 mo, S] |
| `pf.high-round-count` **K** | P S | "That was Alex T.'s 25th round of 40 or better." | count of rounds ≥ own tier T reaches 10/25/50/100/150/200 at S | own tier. 23% | care 3; strength by step (10: 1, 25: 1.25, 50: 1.5, 100+: 2) | Ex `score/count/year \| sh=id, min_score=T`; window [first round, S] (bars add up to the count) |
| `pf.hot-form` | P | "Last 5 Sundays: Pat K. averaged 4.2 above the field's middle score." | mean vs-the-field over the last 5 Sundays shot | ≥ +4; last round within 8 weeks; ≥ 15 rounds. 10/84 | care 3; strength = avg/4 | Ex `adjusted/avg/event \| sh=id`, `ref=0`, `hl=d1..d5`; window [d1 − 1 mo, latest] |
| `pf.up-on-usual` | P | "Last 10 Sundays: Pat K. is 2.8 targets better than their average before that." | mean of last 10 scores − mean of the 20 before | ≥ 2 targets and ≥ 2× noise (noise = standard error of the difference); last round within 8 weeks. 16/84 | care 3; strength = gap/2 | Pg `#trend` with rolling-10 line (**new**), `hl=d1..d10`; window [S − 1 y, S] |
| `pf.beat-own-usual` **K** | P S | "Well above Pat K.'s usual for a day like that: 44 against a usual of 38." | residual at S = score − usual | residual ≥ +5; ≥ 20 prior rounds; P: latest Sunday only. prov. (target P ≤ 15/84) | care 3; strength = residual/5 | Ex `residual/max/event \| sh=id`, `ref=0`, `hl=S`; window [S − 3 mo, S] (label "Vs usual for a day like this"; `label_you` "Vs your usual") |
| `pf.year-up` | P | "Pat K. is averaging 38.4 in 2026 vs 36.9 in 2025, and further ahead of the field too." | this year's mean score − last year's; same for vs-the-field | ≥ 1.5 raw and ≥ 1.0 vs field; ≥ 10 rounds each year. 7/84 | care 3; strength = raw/1.5 | Ex `score/avg/year \| sh=id, best=true`, `cmp=adjusted/avg/year \| sh=id, best=true`, `hl=2026`; window [Jan 1 last year, S] |
| `pf.years-up-run` | P H (Jan) | "Three seasons running, Pat K. has averaged more: 33.1, 35.4, 37.0." | yearly mean score: 2 consecutive rises | each rise ≥ 0.5, total ≥ 1.5; ≥ 10 rounds a year. 9/84 | care 3; strength = total/1.5 | Ex `score/avg/year \| sh=id, best=true`, `hl=y1..y3`; window [Jan 1 y1, S] |
| `pf.gaining-on-field` | P | "Pat K. has gained 2.7 targets on the field in two years." | mean vs-field last 52 weeks − mean vs-field the 52 weeks before; fallback: first 10 rounds → last 10 | 2-year: ≥ 2, ≥ 10 rounds per window. Fallback: ≥ 2, ≥ 30 rounds. 6/84 (+ 25 fallback) | care 3; strength = gain/2 | Ex `adjusted/avg/year \| sh=id`, `ref=0`; window [S − 2 y, S] |
| `pf.low-end-rising` | P | "Pat K.'s off days are getting better: the bottom quarter of rounds is up 3 targets on last year." | 25th-percentile score this year − last year | ≥ 12 rounds each year; ≥ +2 and ≥ 2× noise. prov. (target 5–12/84) | care 3; strength = gain/2 | Ex `score/p25/year \| sh=id, best=true` (**new** agg); window [Jan 1 last year, S] |
| `pf.more-high-rounds` **K** | P S H | "More rounds of 40 or better this year than in all of last year for Pat K.: 14 vs 11." | this year's count of rounds ≥ T > last year's full count | ≥ 8 such rounds last year; S/H on the crossing Sunday only. prov. (target 3–8% of Sundays) | care 3; strength = this/last | Ex `score/count/year \| sh=id, min_score=T`, `hl=2026`; window [Jan 1 last year, S] |
| `pf.best-stretch` **K** | P S H | "Pat K.'s best 10-Sunday stretch ever: 41.3 a round." | mean of the last 10 scores > best earlier 10-round mean | ≥ 30 rounds; + 0.3 over previous best; ≥ career mean + 2; shot in the last 4 weeks. 4/84; ~29% of Sundays | care 4; strength = (mean − career)/2 | Pg `#trend` rolling-10 line (**new**), `hl=d1..d10`; window [S − 6 mo, S] |
| `pf.average-milestone` **K** | P S H | "Pat K.'s 20-Sunday average just went over 35 for the first time." | rolling mean of last 20 scores first crosses 30/35/40/45 upward | crossing within the last 4 rounds; + 1.0 on a year ago. 5/84; 17% of Sundays | care 4; strength by level (30: 1, 35: 1.25, 40: 1.5, 45: 2) | Pg `#trend` rolling-20 line (**new**), `ref=35`, `hl=S`; window [S − 1 y, S] |
| `pf.rating-high` | P H | "Pat K.'s skill rating is at an all-time high, up 1.2 in the last 8 Sundays." (the peak figure itself is on the Stats card, §3.4) | rating at latest Sunday ≥ every earlier value | ≥ 15 rated rounds; rise ≥ 0.5 over 8 Sundays. 8/84 | care 3; strength = rise/0.5 | Pg `/shooters/{id}#rating`, `hl=S`; window [S − 1 y, S] |
| `pf.learning-curve` | P | "Ahead of the usual pace: after 10 Sundays Pat K. averaged 36; new shooters average 34." | mean of the shooter's first 10 rounds − club mean of everyone's first 10 | ≥ club + 2; ≤ 40 Sundays shot. 6/84 | care 3; strength = gap/2 | Pg `#learn`, `hl=10` |

#### 2.2.2 Shooter subject: streaks and kudos runs (5)

| id | pages | sample text | trigger / computation | guard | rank basis | chart link |
|---|---|---|---|---|---|---|
| `pf.above-own-avg-streak` **K** | P S H | "4 Sundays in a row above Pat K.'s own average." | on each of the last k Sundays shot, score > mean of all the shooter's rounds before that Sunday (missed Sundays neither extend nor break it) | ≥ 10 rounds before the run. P: k ≥ 4 and shot in the last 8 weeks. S/H: when k reaches 4/6/8/10/15/20. prov. (target 20–40% of Sundays, P 10–20/84) | care 4; strength = k/4 | Pg `#trend` with "average so far" line (**new**), `hl=run`; window [run start − 3 Sundays, S] |
| `pf.beat-field-streak` **K** | P S H | "Above the field's middle score 7 Sundays in a row for Pat K." | consecutive Sundays shot with vs-field > 0 | P: ≥ 5 and shot in the last 8 weeks (12/84). S/H: when the run reaches 6/10/15/20 | care 4; strength = k/5 | Ex `adjusted/avg/event \| sh=id`, `ref=0`, `hl=run`; window [run start − 2 Sundays, S] |
| `pf.tier-run` **K** | P S H | "9 Sundays in a row at 40 or better for Pat K." | consecutive Sundays shot with score ≥ T | P at the qualifying length 45:4 / 40:6 / 35:8 (14/84). S/H at 2× (45:8 / 40:12 / 35:16; 13%) | care 4; strength = k/length | Ex `score/max/event \| sh=id`, `ref=T`, `hl=run`; window [run start − 2 Sundays, S] |
| `pf.three-rising` **K** | P S | "Scores up 3 Sundays straight for Pat K.: 34 → 37 → 40." | 3 consecutive Sundays shot with strictly rising scores | last score ≥ own average; total rise ≥ 4; ≥ 10 prior rounds. prov. (target 10–25% of Sundays) | care 3; strength = rise/4 | Pg `#trend`, `hl=d1,d2,d3`; window [S − 3 mo, S] |
| `pf.podium-run` **K** | P S | "Third podium in a row for Kim L." | event_rank ≤ 3 on 3+ consecutive Sundays shot | field ≥ 15 each Sunday. 21% | care 4; strength = k/3 | Pg `/shooters/{id}#finishes` (**new** finish strip), `hl=run` |

#### 2.2.3 Shooter subject: milestones, wins, attendance and journeys (15)

| id | pages | sample text | trigger / computation | guard | rank basis | chart link |
|---|---|---|---|---|---|---|
| `pf.wins` **K** | P S H | "First Sunday win of 2026 for Nina O." / "First win of Nina O.'s career." / "3 wins this year." | event_rank = 1 (ties count, as C7) | first-of-year: any (41%); career-first: ≥ 8 prior, field ≥ 15; count: ≥ 2 this year (10/84) | care 5; strength by variant (career 2, first-of-year 1.5, count n/2) | S: Pg `/events/S#results`, `hl=s:id`. P: Ex `wins/sum/year \| sh=id`, `hl=2026` |
| `pf.career-first` **K** | P S H | "First podium of Wes T.'s career: 3rd of 27." | first ever event_rank ≤ 3, or first top-third finish | ≥ 8 prior rounds; field ≥ 15; a first win goes to `pf.wins`. 9% / 7% | care 4; strength podium 1.5, top third 1 | Pg `/events/S#results`, `hl=s:id` |
| `pf.sunday-milestone` **K** | P S H | "100th Sunday for Alex T., one of 24 shooters to get there." / "Alex T. is 3 Sundays from a 50th." | Sundays shot (`shooter_profiles.n_events` as of S) crosses 25/50/100/150/200/250/300 at S; or ≤ 3 to go | crossing: shot S. To go: shot in the last 8 weeks (15/84); the to-go variant is home-only (`pages = {home}`), since the profile's Stats card already shows "Next milestone" (§3.4) | care 4 crossing, 2 to go; strength crossing 25: 1, 50: 1.25, 100: 1.5, 150–200: 1.75, 250+: 2; to go: 1 | Pg `#cal` calendar, `hl=S`; window all |
| `pf.targets-milestone` **K** | P S H | "Pat K. has now broken 5,000 targets on Sundays." | cumulative targets crosses a multiple of 1,000 at S | shown for 4 Sundays after crossing. 5/84 | care 3; strength = min(2, 1 + thousands/10) | Ex `score/sum/year \| sh=id`; window [first round, S] (bars add up to the total) |
| `pf.shooter-anniversary` | P S H | "Three years since Pat B.'s first Sunday: 128 Sundays and a best of 45." | S is the first Sunday on or after the 1/2/3/5/7/10-year date of their first round | shot S; ≥ 12 rounds; not left-censored (C4 `left_censored`). 17% | care 3; strength by years (1: 1, 2–3: 1.25, 5: 1.5, 7–10: 2) | Pg `#cal`, `hl=first,S` |
| `pf.back-strong` | P S H | "Welcome back, Walt R., after 14 months, with a 39, right on their average." | days since previous round ≥ 180 | score shown only if ≥ their prior average; ≤ 3 names on S. 32% | care 3; strength = days/180 | Pg `#cal`, `hl=prev,S`; window [prev − 1 mo, S] |
| `pf.attendance-year` | P H | "Pat K. has shot 33 of 36 Sundays this year." (at 100% of a finished year: "the first perfect year on record") | Sundays attended ÷ held Sundays this year | ≥ 85%; ≥ 8 held so far. 6/84 | care 3; strength = share/0.85 | Pg `#cal`; window [Jan 1, latest] |
| `pf.attendance-streak` | P H | "Pat K. has shot 12 Sundays in a row, their longest run yet." | consecutive held Sundays attended (C7 `streaks`) | P ≥ 5 (4/84); H ≥ 10 | care 3; strength = k/5 | Pg `#cal`, `hl=run` |
| `pf.months-in-row` | P H | "At least one Sunday in each of the last 14 months for Pat K." | consecutive calendar months with ≥ 1 round, ending at the latest month (months with no held Sunday are skipped) | P ≥ 12 (10/84); H ≥ 24 | care 2; strength = months/12 | Pg `#cal` month view, `hl=m1..m14` |
| `pf.charter-shooter` | P | "Pat K. was here on the first Sunday on record, Jan 5, 2020, and is still going." | shot 2020-01-05 and is active | 11 shooters | care 2; strength 1 | Pg `#cal`, `hl=2020-01-05` |
| `pf.year-wrapped` | P H (Dec–Jan) | "Pat K.'s 2025: 41 Sundays, 1,640 targets, best 45, best finish 2nd." | counts and bests for year Y | ≥ 12 Sundays in Y (34/84); shown while the latest Sunday is in Dec Y or Jan Y+1; finish only if top third | care 3; strength 1 | Ex `score/avg/month \| sh=id`; window [Jan 1 Y, Dec 31 Y] |
| `pf.digest-line` | P | "Sunday 9/27: Pat K. shot 38, 4th of 27, 2 over their usual for a day like this." | score, finish and residual at the latest Sunday | shot the latest Sunday; finish only if top half; residual only if ≥ +1 | care 1; strength 1 (pinned first on the profile, not ranked) | Pg `/events/S#results`, `hl=s:id` |
| `pf.rank-climb` | P L H | "41st on the club skill rating a year ago, 22nd today: Pat K." | rating rank among active shooters at S vs S − 364 d | ≥ 8 places, or first time in the top 10. 7/84 | care 3; strength = places/8 (places variant), 1.5 (first-top-10 variant) | Pg `/leaderboards#lb-movers` (**new**), `hl=s:id` |
| `pf.top-of-club` | P | "Pat K. is in the top quarter of the club over the last 12 months." | shooter's mean vs-field over 364 days, placed among active shooters with ≥ 10 rounds | top quarter (9/84); top 10% variant | care 3; strength = 1 / 1.5 | Ex `adjusted/avg/shooter \| from=S−364d, to=S, mr=10`, `s=value_desc`, `hl=s:id` |
| `pf.best-day-vs-field` | P | "Pat K.'s best day against the field: +9 on Jun 1, 2025." | max vs-field over the career | ≥ +10; ≥ +6 only as a fallback when the shooter has no other insight. 31/84 | care 1; strength = best/10 (main), 1 (fallback) | Ex `adjusted/max/event \| sh=id`, `hl=D`; window [D − 3 mo, D + 3 mo] |

#### 2.2.4 Shooter subject: conditions (4, at most 1 on a profile)

| id | pages | sample text | trigger / computation | guard | rank basis | chart link |
|---|---|---|---|---|---|---|
| `pf.wet-strength` | P | "Rain suits Pat K.: +2.1 over the field on wet Sundays, +0.4 on dry." | mean vs-field wet − mean vs-field dry | ≥ 6 wet / ≥ 12 dry rounds; gap ≥ 1.5; wet vs-field ≥ 0; shuffle 90%. 3/84 | care 4; strength = gap/1.5 | Ex `adjusted/avg/precip_band \| sh=id, best=true`, `ref=0`, `hl=wet`; window [first round, S] |
| `pf.weather-steady` | P | "Rain doesn't change Pat K.'s game: the same distance from the field's middle score, wet or dry." | \|wet − dry\| vs-field | ≤ 0.75; 6 wet / 12 dry. 15/84 | care 2; strength = 0.75 / max(gap, 0.25) capped 2 | Ex `adjusted/avg/precip_band \| sh=id, best=true`, `ref=0`; window [first round, S] |
| `pf.best-temp` | P | "Cold suits Pat K.: +2.4 over the field under 40°F." | best band's mean vs-field − mean over the other bands | ≥ 2.0; band ≥ 6 rounds; shuffle 95% (5 bands searched). 4/84 | care 3; strength = gap/2 | Ex `adjusted/avg/temp_band \| sh=id, best=true`, `ref=0`, `hl=band`; window [first round, S] |
| `pf.tough-days` | P | "The tougher the Sunday, the better Pat K. does: +2.6 over the field on the hardest days." | mean vs-field on Sundays with difficulty ≥ 1 − mean on the rest | gap ≥ 1.5; ≥ 6 hard Sundays; shuffle 95%. 4/84 | care 3; strength = gap/1.5 | Pg `/shooters/{id}#tough-days` scatter (**new**) |

#### 2.2.5 Sunday subject (13)

| id | pages | sample text | trigger / computation | guard | rank basis | chart link |
|---|---|---|---|---|---|---|
| `ev.rain-day` (mixed) | S (wet) H | "Rain Sunday. The field shot about the same as on a dry Sunday, and 6 fewer shooters turned out. Better in the rain: Pat K. Rain doesn't slow down: Sam R. and Alex T." | S is wet. Field line: difficulty at S and head count vs prior dry mean. Names from each attendee's prior rounds | always shows on a wet Sunday (field line). Better: ≥ 4 wet / 8 dry prior, gap ≥ 2. Steady: \|gap\| ≤ 0.75 with 6 / 12. ≥ 1 name on 53% of wet Sundays | care 4; strength 1 + names/3 | Ex `attendance/avg/precip_band`, `hl=wet`; window [first held Sunday, S]. Each name links Ex `adjusted/avg/precip_band \| sh=id, best=true`; window [first round, S − 1 d] (prior rounds only, as the guard) |
| `ev.how-it-played` F | S | "A tough Sunday: scores ran about 3 targets under a typical Sunday for this crowd." | difficulty at S; the raw middle score is quoted | \|difficulty\| ≥ 2.5. 14% | care 3; strength = \|d\|/2.5 | Ex `difficulty/avg/event` (**new** metric), `hl=S`, `ref=0`; window [S − 3 mo, S] |
| `ev.toughest-since` F | S | "Toughest Sunday since March." | difficulty at S is the max (or min) over the prior 26 weeks | \|difficulty\| ≥ 2. 9% | care 3; strength = weeks/26 | Ex `difficulty/avg/event`, `hl=prev,S`; window [prev − 2 wk, S] |
| `ev.spotlight` | S H | "Biggest day of the Sunday: Dave M. shot 44, 8 more than their usual for a day like this." | residual at S, top 3 | residual ≥ 7; ≥ 20 prior rounds; ≤ 3 names. 68% | care 4; strength = residual/7 | Ex `residual/max/shooter \| from=S, to=S`, `s=value_desc`, `hl=s:id` |
| `ev.week-jump` | S H | "Biggest jump from the Sunday before: Dana K., with a 43." (the earlier score and the size of the jump are never shown) | score at S − the shooter's score on their previous Sunday shot (within 6 weeks) | ≥ 10; new score ≥ usual and ≥ field's middle; ≥ 12 prior; ≤ 2 names; not a name already in `ev.spotlight`. 29% | care 3; strength = jump/10 | Ex `score/max/event \| sh=id`, `hl=prev,S`; window [S − 6 wk, S] |
| `ev.close-finish` | S H | "Tie at the top: Ethan S. and Stanton F. both shot 49." / "Top 3 within one target." | top two equal; or top 3 within 1 | field ≥ 15; top-3 variant needs top ≥ 45. 21% / 12% | care 4; strength tie 1.5, within-1 1 | Pg `/events/S#results`, `hl=top` |
| `ev.record-watch` | S H | "Kay T. shot 49, one off the club record of 50." | any round ≥ 48 at S | 19%. Supersedes `ev.top-score` | care 4; strength = 1 + (score − 48)/2 | Pg `/records#rec-highest`, `hl=round:{id}` |
| `ev.top-score` | S H | "Top score 48: one of the best top scores of the last 3 years." | top score at S is in the top 10% of Sunday top scores over the prior 3 years | 8% | care 3; strength 1 | Ex `score/max/event`, `hl=S`; window [S − 3 y, S] |
| `ev.new-faces` | S H | "Welcome to 3 first-timers. Ellie F. opened with a 38, better than 70% of first rounds here." | first rounds at S; strong start = score beats ≥ 70% of all prior first rounds and ≥ field's middle | welcome: any (45%); strong start 10% | care 3; strength = 1 (+0.5 strong start) | Pg `/club#first-rounds` histogram (**new**), `hl=38`; names link Pg `/events/S#results`, `hl=s:id` |
| `ev.second-visit` | S H | "Second visit for Alton U. and Jo P. Welcome back." | exactly 1 prior round, within 10 weeks | no scores shown. 24% | care 2; strength 1 | Pg `/events/S#results`, `hl=s:ids` |
| `rec.drought-clock` F | R S H | "17 Sundays since the last 49." | Sundays since the last round ≥ 49; no names | wait ≥ 16 (2× the median wait of 8). 24% | care 3; strength = wait/16 | Ex `score/max/event`, `ref=49`, `hl=last,S`; window [last − 1 mo, S] |
| `ev.drought-ended` | S H R | "Kay T.'s 49 ends a 17-Sunday wait for a round that high." | a round ≥ 49 at S after a wait ≥ 16 Sundays | as `rec.drought-clock`; ≤ 3 names. 3% | care 4; strength = wait/16 | same chart as `rec.drought-clock`, `hl=last,S` |
| `home.sunday-recap` (mixed) | H | "Sunday 9/27: 27 shooters on a cool, breezy morning. Scores ran a little tougher. Kay T. topped the board with a 48, 5 set a personal best and 3 first-timers joined us." | composite of slots: crowd + weather, how it played, winner, PB count, first-timers; each slot is its own insight's params | ≥ 3 slots pass; every Sunday. Line clamp 3 with "Show all" (§3.8) | pinned (hero slot rules §3.4 do not apply); strength 1 | header Pg `/events/S#results`; each slot links its own chart |

#### 2.2.6 Club subject (10)

| id | pages | sample text | trigger / computation | guard | rank basis | chart link |
|---|---|---|---|---|---|---|
| `cl.rain-turnout` F | C H | "Rain keeps about 6 shooters home: 19 on wet Sundays vs 25 on dry." | mean head count wet − dry, every Sunday with weather and a head count (same rule as Plan 11 T2 turnout) | gap ≥ 3 and ≥ 2× noise; ≥ 20 wet Sundays. Fires (−6.1, noise 1.2) | care 4; strength = gap/3 | Ex `attendance/avg/precip_band` |
| `cl.rain-scores` F | C | "Rain barely moves our scores: a wet Sunday plays within half a target of a dry one." | mean difficulty wet − dry. Neutral twin when within 2× noise; field-negative twin when ≥ 1.5 and ≥ 2× noise | Fires as the neutral twin (+0.13, noise 0.24) | care 2; strength 1 | Ex `difficulty/avg/precip_band`, `ref=0` |
| `cl.weather-scoreboard` F | C | "Rain, wind and cold barely move our scores here. Turnout is what changes." | the same test over precip, gust and temp bands (85+ excluded: 6 Sundays) | all within noise → neutral headline; else names the band that moves scores | care 2; strength 1 | Ex `difficulty/avg/wind_band`, `ref=0`; "also" links for temp and precip |
| `cl.turnout-trend` F | C H | "Turnout has climbed 3 seasons running: 22 → 27 shooters a Sunday." | yearly mean head count; or last 8 Sundays vs the 8 before | 3 rising years; or 8-vs-8 ≥ 15% and ≥ 2× noise (19%) | care 3; strength = rise/15% (8-vs-8 variant), 1.5 (3-rising-years variant) | Ex `attendance/avg/year`; window [first held Sunday, S] |
| `cl.newcomers` | C H | "38 new shooters in 2026; 14 have come back for more." | first rounds this year; came back = ≥ 2 Sundays | ≥ 10 first-timers | care 3; strength = n/10 | Pg `/club#new`, `hl=2026` |
| `cl.originals` | C H | "11 of the 14 shooters from our first Sunday on record still shoot." | shooters at 2020-01-05 who are active | ≥ 3 | care 3; strength 1 | Ex `rounds/count/year \| sh=charter ids`; window [2020-01-05, S] (`attendance` rejects shooter filters) |
| `cl.year-wrap` | C H | "2025 in numbers: 48 Sundays, 1,244 rounds, 57 first-timers; busiest Sunday Aug 17 with 40." | totals for the latest finished year; "rounds" = round rows (the Explorer `rounds` metric), not `head_count` | ≥ 30 Sundays in that year; H only Dec–Feb | care 3; strength 1 | Ex `rounds/count/year`, `hl=2025`; window [first held Sunday, S] |
| `cl.year-pace` F | C H | "2026 has passed all of 2025: 1,245 rounds by Sunday 44." | rounds to date vs the same date in each earlier year | C: ≥ 5% ahead (silent at +3.5% now). H: only on a crossing (first Sunday ahead, or passed last year's total) | care 3; strength = lead/5% (C), 1.5 (H crossing variants) | Ex `rounds/count/year` with same-date cutoff (**new** `ytd=MM-DD`); window [first held Sunday, S] |
| `cl.club-one-shooter` | C | "If the club were one shooter: a 34.9 average, 41st of the 70 shooters with 5 or more rounds in the last 12 months." | mean of all best rounds in the 364 days to S, placed among shooters with ≥ 5 rounds in that window (text and chart use this one population) | always | care 2; strength 1 | Ex `score/avg/shooter \| from=S−364d, to=S, mr=5, best=true`, `s=value_desc`, `ref=34.9` |
| `rec.perfect-rarity` | R H | "5 perfect 50s in 7,300 rounds; 29 rounds of 49 or better." | counts over all rounds | ≥ 1 perfect round | care 2; strength 1 | Pg `/records#rec-highest` |

#### 2.2.7 Season, records and stations (9)

| id | pages | sample text | trigger / computation | guard | rank basis | chart link |
|---|---|---|---|---|---|---|
| `lb.new-leader` | L H | "New season points leader: Maria O. moved into 1st." | season points leader after S ≠ leader before S | after Sunday 6; lead ≥ 1. 9 changes in 2026 | care 4; strength 1.5 | Pg `/race#race-bars` (**new**), `hl=s:id`; window season |
| `lb.title-race` | L H | "Season race: Dale R. leads by 4 points." / "Dale R. has the 2026 title in hand." (only the leader is named; the runner-up is never named as trailing, D9) | gap between 1st and 2nd in season points | race: gap ≤ 11 after Sunday 6. Clinched: gap > 11 × Sundays left before Dec 31 (calendar bound) | care 3; strength = 11/max(gap,1) capped 2 (race), 2 (clinched) | same chart |
| `lb.biggest-climb` **K** | L H | "Up 3 places in season points: Casey L. is now 5th." | season points rank after S − rank before S | ≥ 3 places; new rank ≤ 10; after Sunday 6. prov. (target 15–30% of Sundays) | care 3; strength = places/3 | same chart, `hl=s:id` |
| `lb.most-improved` **K** | L H P | "Most improved this season: Jordan M., skill rating up 3.4 since January." | C7 `most_improved` Δ for period `season` | C7 eligibility; Δ ≥ 1.0; top 1 (L shows top 3). Kudos anchor = the Sunday the Δ last rose (§3.4). prov. | care 4; strength = Δ/1 | Pg `/leaderboards?metric=most_improved&period=season#lb-board`, `hl=s:id` |
| `rec.streak-chase` | R H | "Three shooters are on runs of 15+ Sundays; the record is 58." | current attendance streaks vs the longest ever; win streak within 1 of the record | ≥ 15 current, or within 1 of a record | care 3; strength = run/15 (attendance variant), 1.5 (win-streak variant) | Pg `/records#rec-streaks`, `hl=s:ids` |
| `st.hardest-easiest` F (dormant) | St | "Station 7 is the toughest stand: the field breaks 61% there vs 76% overall." | per-station hit % over the current layout era | ≥ 8 station Sundays and ≥ 30 entries per station | care 3; strength = spread/10 pts | Pg `/stations#hit-rate`, `hl=7` |
| `pf.station-best` (dormant) | P St | "Station 4 is Pat K.'s station: 94% vs 82% for the field." | shooter hit % − field hit % per station; best one | as above, plus ≥ 4 Sundays at that station; gap ≥ 8 points | care 3; strength = gap/8 | Ex `hit_pct/avg/station \| sh=id`, `cmp=hit_pct/avg/station` (same spec without `sh`), `hl=4`; window [layout era start, S] |
| `pf.trophy-rare` (dormant) | P H | "Pat K. earned Perfect Round, a trophy only 3 shooters hold." / "first ever holder" | holders of that trophy code | ≤ 5 holders or ≤ 5% of active; awarded in the last 4 Sundays | care 4; strength = 5/holders | Pg `/shooters/{id}#trophies`, `hl=code` |
| `pf.next-trophy` (dormant) | P | "Pat K. is two 45+ rounds from Sharp Shooter." | registry `progress` remaining to the next tier | remaining ≤ 2 units or ≤ 10%; shot in the last 8 weeks | care 2; strength 1 | Pg `/shooters/{id}#trophies` progress bar, `hl=code` |

**Count check:** 18 + 5 + 15 + 4 + 13 + 10 + 9 = 74 (`rec.drought-clock` was split into the name-free clock and `ev.drought-ended`, §8 C2). Kudos kinds (K): 20.

**Coverage target (golden, §5):** with v1 guards, ≤ 9 of 84 active shooters have no profile insight (CATALOG §2 coverage), and those nine are mostly shooters with 5–10 rounds.

#### 2.2.8 Family and home slot per kind

`family` drives "one per family" (§3.4); `home_slot` places a kind in one of the four home cards (§3.4). A kind whose pages do not include H has no home slot in practice. Both are `Kind` fields (§3.3) and are stored on each row.

| family | kinds | home_slot |
|---|---|---|
| `form` | `pf.hot-form`, `pf.up-on-usual`, `pf.beat-own-usual`, `pf.year-up`, `pf.years-up-run`, `pf.gaining-on-field`, `pf.low-end-rising`, `pf.best-stretch`, `pf.season-best`, `pf.rating-high`, `pf.learning-curve`, `pf.top-of-club`, `pf.best-day-vs-field`, `ev.spotlight`, `ev.week-jump` | `person` |
| `streak` | `pf.above-own-avg-streak`, `pf.beat-field-streak`, `pf.tier-run`, `pf.three-rising`, `pf.podium-run`, `pf.attendance-streak`, `pf.months-in-row`, `pf.attendance-year` | `person` |
| `milestone` | `pf.pb`, `pf.tied-best`, `pf.first-tier`, `pf.first-since`, `pf.high-round-count`, `pf.more-high-rounds`, `pf.average-milestone`, `pf.sunday-milestone`, `pf.targets-milestone`, `pf.shooter-anniversary`, `pf.career-first`, `pf.charter-shooter` | `milestone` |
| `race` | `pf.wins`, `pf.rank-climb`, `ev.close-finish`, `lb.new-leader`, `lb.title-race`, `lb.biggest-climb`, `lb.most-improved` | `race_record` |
| `record` | `ev.record-watch`, `ev.top-score`, `rec.drought-clock`, `ev.drought-ended`, `rec.perfect-rarity`, `rec.streak-chase` | `race_record` |
| `weather` (weather and how the day played) | `pf.wet-strength`, `pf.weather-steady`, `pf.best-temp`, `pf.tough-days`, `ev.rain-day`, `ev.how-it-played`, `ev.toughest-since`, `cl.rain-scores`, `cl.weather-scoreboard` | `field` |
| `turnout` | `cl.rain-turnout`, `cl.turnout-trend`, `cl.year-pace`, `cl.club-one-shooter` | `field` |
| `newcomer` | `ev.new-faces`, `cl.newcomers`, `cl.originals` / `ev.second-visit`, `pf.back-strong` | `field` / `person` |
| `station` | `st.hardest-easiest`, `pf.station-best` | none |
| `trophy` | `pf.trophy-rare`, `pf.next-trophy` | `milestone` |
| `recap` | `home.sunday-recap`, `pf.digest-line`, `pf.year-wrapped`, `cl.year-wrap` | none (pinned, or seasonal "More") |

15 + 8 + 12 + 7 + 6 + 9 + 4 + 5 + 2 + 2 + 4 = 74.

### 2.3 Later list (147 kinds, by name)

Built with the same engine when wanted; guards from CATALOG §1–§2 and §6.2.

| Group | Kinds |
|---|---|
| Conditions (13) | `pf.wind-strength`, `pf.big-field`, `pf.best-season`, `pf.no-rust`, `pf.rain-regular`, `ev.cold-heat-day`, `ev.windy-day`, `ev.weather-explained`, `ev.weather-twin`, `ev.weather-record`, `cl.cold-turnout`, `cl.best-season`, `cl.crowd-size` |
| Form and consistency (6) | `pf.steady`, `pf.beat-field-share`, `pf.near-the-top`, `pf.points-pace`, `pf.record-average-pace`, `pf.trophy-count` |
| Sunday page, round 1 (7) | `ev.last-year`, `ev.turnout`, `ev.field-tightness`, `ev.big-climb`, `ev.regulars-on`, `ev.vs-last-sunday` |
| Stations, dormant (13) | `pf.station-day`, `pf.station-steady`, `pf.station-climbing`, `pf.hard-stand`, `pf.station-first-clean`, `ev.station-today`, `ev.station-vs-history`, `ev.station-clean-few`, `st.reset-change`, `st.separator`, `st.clean-rate`, `st.wind-x-station`, `st.rain-x-station` |
| Home and club, round 1 (18) | `home.this-week-in-history`, `home.club-milestone`, `home.anniversary`, `home.club-hot-hand`, `cl.turnout-month`, `cl.holiday`, `cl.winning-score-trend`, `cl.field-trend`, `cl.parity-winners`, `cl.field-spread`, `cl.close-races`, `cl.retention`, `cl.conversion`, `cl.core-regulars`, `cl.member-guest-mix`, `cl.tradition-week`, `cl.bounce-back`, `cl.best-sunday-of-year` |
| Leaderboards and records, round 1 (3) | `lb.rating-crown`, `lb.neck-and-neck`, `rec.tribute` (needs a club opt-in flag) |
| Profile, round 2 (32 + 2 dormant) | `pf.arc`, `pf.year-ago-today`, `pf.holiday-loyal`, `pf.score-bingo`, `pf.favorite-score`, `pf.same-score-run`, `pf.near-pb`, `pf.pb-ladder`, `pf.crossed-field-middle`, `pf.tight-band`, `pf.tightening`, `pf.every-month`, `pf.strong-finish`, `pf.fast-start`, `pf.momentum-carry`, `pf.rises-to-hot-days`, `pf.top-third-finishes`, `pf.rating-since-start`, `pf.milestone-pace`, `pf.years-running`, `pf.year-openers`, `pf.seasonal-regular`, `pf.coldest-shot`, `pf.passed-last-year`, `pf.sundays-vs-best-year`, `pf.best-finish`, `pf.big-crowd-finish`, `pf.club-share`, `pf.cohort-mates`, `pf.first-sunday-crowd`, `pf.circle-size`, `pf.crew` (opt-out), and dormant `pf.trophy-tier-up`, `pf.trophy-set-complete` |
| Sunday page, round 2 (23 + 1 dormant) | `ev.tag-chips`, `ev.forty-plus-count`, `ev.targets-broken-today`, `ev.holiday-sunday`, `ev.year-opener`, `ev.after-skip`, `ev.season-first-weather`, `ev.weather-run`, `ev.week-turnout-rank`, `ev.week-weather-rank`, `ev.season-opener`, `ev.wet-turnout-best`, `ev.experience-today`, `ev.reunion-sunday`, `ev.core-out-in-force`, `ev.pair-milestone`, `ev.debut-cohort`, `ev.score-twins`, `ev.repeat-top-score`, `ev.same-as-last-week`, `ev.twin-sunday`, `ev.perfectly-average`, `ev.round-total`, and dormant `ev.trophy-haul` |
| Home, round 2 (3 + 1 dormant) | `home.year-first-score`, `home.roster-milestone`, `home.usual-crowd`, and dormant `home.year-first-trophy` |
| Club, round 2 (16 + 2 dormant) | `cl.cohort-survival`, `cl.cohort-growth`, `cl.new-regulars`, `cl.newcomer-fast-start`, `cl.newcomer-season`, `cl.returners`, `cl.turnout-floor`, `cl.unbroken-run`, `cl.big-days-count`, `cl.forty-share`, `cl.favorite-score`, `cl.common-winning-score`, `cl.more-improving`, `cl.season-ramp`, `cl.halfway-report`, `cl.rain-or-shine`, and dormant `cl.trophy-popular`, `cl.trophies-year-pace` |
| Leaderboards and records, round 2 (7) | `rec.run-boards`, `rec.year-best-rounds`, `rec.high-round-year`, `lb.podium-lock`, `lb.defending-champ`, `lb.repeat-champs`, `lb.steadiest` |

Round 1 later: 60 (the 69 of CATALOG §4, minus 6 promoted in §5, minus 3 class kinds). Round 2 later: 87 (88 minus `pf.class-cushion`). Total 147. `ev.tag-chips` reuses v1 thresholds and is the cheapest next add.

**D9 check before any later kind is built.** A later kind ships only if no named clause places one named shooter relative to another. The ones to watch: `lb.neck-and-neck` and `lb.podium-lock` may name shooters only as sharing a standing ("Dale R. and Alton U. are level on 88 points"), never as ahead/behind; `ev.score-twins`, `pf.cohort-mates`, `pf.crew` and `pf.circle-size` describe who shot together, never who beat whom; `pf.no-rust` and `pf.near-the-top` compare the shooter with their own history or the field only. Each must also pass the §4.2 D9 lint and the Stats-card overlap rule (§3.4).

### 2.4 Dropped (28 kinds)

| Dropped | Reason |
|---|---|
| `ev.class-winners`, `pf.class-climb`, `pf.class-reach`, `lb.class-watch`, `pf.class-standing`, `pf.class-cushion`, `lb.class-cutoff`, `lb.class-gap` | **D3.** "Class" would be confused with NSCA shooting classes, and the rating classes are being removed from the app. The positive intent survives in `pf.rating-high`, `pf.rank-climb` and `lb.most-improved`. |
| Head-to-head tally (PR39, CO30) | Names a rival as the one losing (D1, D9), and fires for 681 of 782 active pairs. |
| `ev.upset-winner` | D9: framed as beating a favourite (the app's "upset" notable and Giant Killer trophy are also being removed). |
| Named bounce-back (WC12 named) | Built on bad rounds; mostly regression to the mean. |
| Gauge specialist / gauge neutral pair, gauge shines today | Gauge recorded on 2.4% of rounds. |
| Super sporting specialist, round type vs usual | Round type unknown on 308 of 310 Sundays. |
| Points still in play (CO4) | Needs a season schedule; would present an estimate as fact. |
| `ev.second-rounds`, `pf.second-round-lift` | Only 39 second rounds. |
| `ev.namesake-day`, `pf.namesakes` | No household data; surname guessing is a privacy risk. |
| `pf.rebound-after-tough-day` | Near the dropped named bounce-back. |
| `lb.points-year-pace`, `pf.targets-year-pace` | Year-end projections need a schedule. |
| `ev.past-winners-present` | Median 11 past winners in every field: not news. |
| `cl.field-steady` | Always true. |
| `ev.clock-change` | Noise. |
| `ev.milestone-day`, `ev.rain-crew`, `pf.tier-journey`, `home.on-deck`, `home.perfect-attendance-alive` | Near-duplicates, folded into `pf.sunday-milestone`, `pf.rain-regular`, `pf.first-tier`, `pf.sunday-milestone` and `pf.attendance-year` templates. |
| Plan 06 profile "rust" line as an insight | Not made into an insight kind: as a sentence it would describe time away as a cost. The number itself **stays** on the profile Stats card ("after 3+ weeks off", 28-day gap) as a neutral stat (D12, §3.7). `pf.back-strong` is the welcoming insight for a return. |

(7 Appendix A + 13 round-2 + 8 class = 28. 73 + 147 + 8 class = 228 kept kinds in the catalog before D3; the `rec.drought-clock` split makes v1 74.)

---

## 3. Architecture

### 3.1 Tables (migration: the next free number in `backend/migrations/versions/` at plan time, owned by Phase 1a T1 alone in its wave, per C4)

Today the next number is `0003`. Class removal (Phase 0 T1) needs no migration (classes are computed on demand, C6); if it turns out to need one, it takes `0003` and insights takes `0004`. The plan fixes the number; the spec does not.

**`insights`**: one row per rendered insight, fully replaced by each recompute.

| column | type | notes |
|---|---|---|
| `id` | bigserial PK | not stable across generations; never exposed |
| `key` | text NOT NULL UNIQUE | stable identity: `sha1(kind, subject_type, subject_id, anchor_date, variant)[:20]`; roll-up cards get `sha1(kind, 'rollup', anchor_date)[:20]`. Used for the "New" chip, phrasing choice, hero history and URLs |
| `value_hash` | text NOT NULL | `sha1` of the params that appear in the headline; an evergreen row whose numbers change (3 wins → 4 wins) keeps its `key` but gets a new `value_hash` |
| `generation` | int NOT NULL | the `data_version` this row belongs to (= `get_data_version() + 1` inside the step, which equals the value `run_pipeline` bumps to) |
| `first_generation` | int NOT NULL | carried over from the previous row with the same `key` **and** `value_hash`, else `generation`; "New" chip = `first_generation == generation` |
| `kind` | text NOT NULL | registry id, e.g. `pf.pb` |
| `family` | text NOT NULL | §2.2.8 |
| `home_slot` | text NULL | `field, person, milestone, race_record`, or NULL (§2.2.8) |
| `subject_type` | text NOT NULL | `shooter, sunday, club, season, station` |
| `subject_id` | text NOT NULL | `'182'`, `'2026-09-27'`, `'club'`, `'2026'`, `'7'` |
| `anchor_date` | date NULL | the Sunday it is about; NULL = evergreen |
| `variant` | text NOT NULL | the Fact's variant (`'profile'` for the evergreen profile row of a kind with separate page guards, below) |
| `pages` | text[] NOT NULL | computed per Fact from that kind's per-page guards; subset of `{profile, sunday, home, club, leaderboards, records, stations}` |
| `expires` | jsonb NOT NULL DEFAULT '{}' | per-page expiry in later held Sundays, e.g. `{"home": 3, "profile": 8}`; a page missing from the map never expires. Sunday pages ignore it. Anchored kinds default to `{"home": 3, "profile": 3}`; a kind may override per page |
| `named_shooter_ids` | int[] NOT NULL DEFAULT '{}' | everyone named in the text (subject included) |
| `polarity` | text NOT NULL | `CHECK (polarity IN ('positive','neutral','field_negative','mixed'))` and `CHECK (polarity <> 'field_negative' OR cardinality(named_shooter_ids) = 0)`. `mixed` = the card has a name-free field clause that may be negative and named clauses that are positive or neutral (§3.3) |
| `kudos` | bool NOT NULL | the kind is a kudos kind and the row has a kudos anchor (§3.4) |
| `template_id` | text NOT NULL | `'{kind}:{variant}:{n}'`; which phrasing was chosen (§3.5) |
| `params` | jsonb NOT NULL | every number and name in the text, sample sizes, guard values, the evidence window; the single source for headline, explainer, chart and tests |
| `strength` | real NOT NULL | ≥ 1 (clamped, §3.3) |
| `rank_score` | real NOT NULL | §3.4 |
| `headline` | jsonb NOT NULL | rendered segments, third-person variant (§3.5) |
| `headline_you` | jsonb NULL | second-person variant, shooter subjects only |
| `how` | jsonb NOT NULL | 1–3 "How we worked it out" bullets, third person |
| `how_you` | jsonb NULL | second-person `how`, shooter subjects only |
| `chart` | jsonb NOT NULL | §3.6; includes `label` and `label_you` |

Indexes: `(subject_type, subject_id)`, GIN `(pages)`, `(anchor_date)`, GIN `(named_shooter_ids)`.

**Kinds with separate page guards.** When a §2.2 row gives different rules for S/H and for P (`pf.pb`, `pf.above-own-avg-streak`, `pf.beat-field-streak`, `pf.tier-run`, `pf.sunday-milestone`, `pf.attendance-streak`, `pf.months-in-row`, `pf.more-high-rounds`, `pf.wins`), the generator emits two kinds of Fact:
- **Anchored** (variant as in the table, `anchor_date = S`, `pages ⊆ {sunday, home}`): fires at the crossing Sunday under the S/H guard.
- **Evergreen profile** (variant `profile`, `anchor_date` NULL, `pages = {profile}`): evaluated once as of the latest held Sunday under the P guard (for example `pf.pb`: the latest PB, if set in the last 52 Sundays).

All other anchored kinds that list P emit one row with `profile` in `pages` and use `expires.profile` (default 3, overridden where a row says so, for example `pf.first-tier` 12, `pf.career-first` 12). The selection tests (§5) cover each page's expiry.

**`insight_picks`**: the rotation results the selection rules need history for, computed in the same step.

| column | type | notes |
|---|---|---|
| `sunday` | date | a held Sunday |
| `slot` | text | `hero`, `spotlight` |
| `insight_key` | text | the pick for that Sunday's home page |
| PK | `(sunday, slot)` | |

### 3.2 Recompute step `analytics/steps/s60_insights.py` (order 60, after `s50 achievements`)

| Step | Detail |
|---|---|
| 1 | `clear_cache()` first (as s50), so the loaders see frames written earlier in this transaction. |
| 2 | Load once: `load_rounds`, `load_events` (incl. difficulty, head count, weather bands), `load_rating_history`, `load_station_hits`, `load_shooters` (incl. `n_events`, `left_censored`), achievements (`achievements_awarded` + registry progress), season points (Plan 09 `points.py`). Build an `InsightFrames` bundle. |
| 3 | `Readiness` = `{station_sundays, trophy_awards, latest_sunday}`; dormant kinds are skipped when their `requires` is unmet (§4.5). |
| 4 | Evaluate every registered kind. Sunday-anchored kinds run for **every held Sunday** S on frames sliced to `event_date ≤ S` (baselines use `< S`). Evergreen shooter, club, season and station kinds run once, `as_of` = latest held Sunday. |
| 5 | Clamp strengths (§3.3), rank (§3.4), render text (§3.5), build chart links (§3.6), compute `insight_picks` Sunday by Sunday in date order using only picks for earlier Sundays. |
| 6 | Read `(key, value_hash, first_generation)` from the current table, then `DELETE FROM insights; DELETE FROM insight_picks;` and bulk-insert, all in the pipeline transaction. A rollback of the upload rolls these back too. |

- **Never raises on data.** s60 runs inside the upload's transaction, so nothing in it asserts on data values. Out-of-range values are clamped and logged (`insights.clamp kind=… key=…`). Registry and spec errors are caught by CI (§3.3, §5), not at recompute time.
- **Idempotent full replace:** the same data gives the same rows (seeded shuffles, deterministic ordering by `(kind, subject, anchor, variant)`, template choice keyed by `key` alone, §3.4), and running the step twice leaves identical content except `generation`.
- **Static until data changes (D5):** nothing uses the wall clock. Seasonal windows (Dec–Jan wrap-ups, "this year") key off the latest held Sunday. The API only reads. Any pipeline run (upload commit, rollback, rule change, merge, admin recompute, weather-sync recompute) refreshes insights; because phrasing is keyed by `key`, a refresh with unchanged data rewords nothing.
- **Weather arrives one run later.** The rebuild handler enqueues `weather_sync`, which enqueues `recompute` after it writes window hours. So a new Sunday's `ev.rain-day`, the conditions card and the other weather kinds appear after that second recompute, not with the upload.
- **Budget:** measured in Phase 1a on the full dataset (310 Sundays) with the first kinds, extrapolated per kind, and recorded in the plan. The target is ≤ 30 s. Per-Sunday work reuses prefix aggregates (running max, running mean, streak counters) rather than re-slicing frames 310 times where a kind allows it. The performance test asserts the recorded time × 2 and runs under the `slow` pytest marker only.
- Exclusions: deceased shooters (`rec.tribute` stays on the later list pending an opt-in flag), and any shooter below the kind's own guard.
- Filters: insights ignore the global round-type filter and status/gauge filters (ruling 3); the explainer says "All round types", and chart links clear the filter (§3.6.1).

### 3.3 Rule registry `analytics/insights/`

Same pattern as `analytics/achievements/registry.py`: sibling modules (`form.py`, `streaks.py`, `milestones.py`, `conditions.py`, `sunday.py`, `club.py`, `season.py`, `stations.py`, `trophies.py`) call `register(Kind(...))` at import; `load_all()` imports every non-underscore module via `pkgutil`.

```python
class Polarity(StrEnum):
    POSITIVE = "positive"; NEUTRAL = "neutral"; FIELD_NEGATIVE = "field_negative"; MIXED = "mixed"

@dataclass(frozen=True, kw_only=True)
class Kind:
    id: str                                   # 'pf.pb'
    family: Family                            # §2.2.8
    home_slot: HomeSlot | None                # §2.2.8
    subject: SubjectType                      # shooter | sunday | club | season | station
    pages: frozenset[Page]                    # the pages it may show on; each Fact narrows this
    polarity: Polarity
    care: int                                 # 1–5
    anchored: bool                            # True ⇒ evaluated per held Sunday (no-leak slice)
    guard: Mapping[str, float]                # named constants, quoted by the explainer
    templates: tuple[Template, ...]           # 1–3 phrasing variants, same params (§3.5)
    how: tuple[Template, ...]                 # "How we worked it out" bullets (with _you twins for shooter subjects)
    chart: Callable[[Params], ChartLink]      # §3.6; builds spec + explicit window from params
    proof: tuple[ProofCheck, ...]             # how each headline number is found in the chart result (§5)
    evaluate: Callable[[InsightFrames, Scope], Iterable[Fact]]
    kudos: bool = False
    expires: Mapping[Page, int] = DEFAULT_EXPIRES   # {'home': 3, 'profile': 3} for anchored kinds
    requires: Requires = Requires()           # e.g. Requires(station_sundays=8), Requires(trophy_awards=1)
    supersedes: frozenset[str] = frozenset()  # kinds hidden when this one fires for the same subject/anchor
```

- `Fact(subject_id, anchor_date, variant, pages, params, strength, named_shooter_ids)` is the only thing a generator returns. It never builds text. `pages` is the kind's pages narrowed by the per-page guards.
- **Per-clause polarity.** A template is a sequence of clauses, each tagged `field` or `named`. A `field` clause may not contain a `Shooter` or `NameList` slot and may be negative about the club or the field ("6 fewer shooters turned out", "scores ran a little tougher"). A `named` clause must be positive or neutral. A kind is `mixed` when it has both (`ev.rain-day`, `home.sunday-recap`).
- **Import-time validation** (fails the registry load, so CI fails):
  - `field_negative` kinds have no `named` clauses and `subject != shooter`.
  - `subject == shooter` kinds are `positive` or `neutral`.
  - In `mixed` kinds, every clause containing a `Shooter`/`NameList` slot is tagged `named`, and every `field` clause has none.
  - Every template slot exists in the kind's declared params schema; every kind has ≥ 1 template, ≥ 1 `how` bullet, a `chart` builder, a `proof` entry for every numeric headline param, a `family`, and a `home_slot` when `home ∈ pages`.
  - D9: in a `named` clause, two name slots appear only in a list shape, with none of "ahead", "behind", "lead", "beat", "over", "than" in the text between them (§4.2).
- **Strength ≥ 1 is a registry property, not a runtime assert.** Each kind's unit test evaluates a frame at the edge of every variant's guard and asserts `strength ≥ 1`. In production, s60 clamps `strength = max(1, strength)` and logs a warning; it never raises (§3.2).
- Named-shooter generators return nothing unless the favourable condition holds. There is no softened negative variant.

### 3.4 Ranking and selection

**Score:** `rank_score = care × min(strength, 2) × recency × rarity`

| factor | rule |
|---|---|
| recency | Relative to the **reference Sunday R**: the latest held Sunday for the live feeds, and the pick Sunday when `insight_picks` is computed for a past Sunday. 1.5 when `anchor_date` = R; × 0.8 for each held Sunday between them; hidden from a page after that page's `expires` count. Evergreen = 1.0. On a Sunday page, every insight anchored to that Sunday has recency 1.5. |
| rarity | `clamp(0.5 + log2(1 / share) / 2, 1, 3)`. `share` = the fraction of eligible subjects that got this kind, where eligible subjects are: evergreen shooter kinds, active shooters as of R; anchored shooter kinds, shooter-Sundays (rounds at held Sundays) over the last 52 held Sundays up to R; Sunday kinds, held Sundays over the same 52; club, season, station kinds, rarity 1. 3 of 84 → 2.9; 23 of 84 → 1.4; half or more → 1. |

**Page sizes and feeds**

| Page / subject | Top shown | Candidate pool |
|---|---|---|
| Profile `shooter:{id}` | 3 + pinned `pf.digest-line` | rows with `subject = shooter:{id}` and `profile ∈ pages`, not expired for `profile`. Visible to every logged-in viewer on every profile, digest line included (D11) |
| Sunday `sunday:{date}` | conditions card (wet in v1; cold and windy when `ev.cold-heat-day` and `ev.windy-day` ship) + 3 + kudos strip | rows with `anchor_date = date` and `sunday ∈ pages` (Sunday subjects + shooter rows anchored there, grouped into roll-ups) |
| Home | recap (pinned) + hero + 4 (one per `home_slot`: `field`, `person`, `milestone`, `race_record`; an empty slot is filled by the next best row of any slot) + kudos strip | rows anchored to the last 2 held Sundays or evergreen, with `home ∈ pages`, not expired for `home` |
| Club | 3 | club subjects |
| Leaderboards | 2 | season subjects + `lb.*` shooter rows |
| Records | 2 | `rec.*` and `ev.drought-ended` |
| Stations | 2 | station subjects (dormant until ready) |

**Kudos.** The kudos strip shows kudos rows whose kudos anchor is the page's Sunday (home: the latest held Sunday). For Sunday-anchored K kinds the kudos anchor is `anchor_date`. For the season `lb.*` K kinds (`lb.biggest-climb` is already anchored; `lb.most-improved` is a period value) the kudos anchor is the Sunday on which the value last rose, stored in `params.kudos_sunday`; the row itself stays evergreen for the leaderboards page. **Cap (D10):** the strip shows at most 10 chips (ranked by the chip's `rank_score`); when there are more, an 11th chip "and N more" opens the full list in a `Sheet`. The feed's `kudos` list is uncapped, so the full list needs no second request.

**Variety and dedupe (applied in this order to the ranked candidates)**

| Rule | Effect |
|---|---|
| Supersedes | `pf.pb` hides `pf.season-best`, `pf.tied-best`, `pf.first-tier` and `pf.best-day-vs-field` for the same shooter and Sunday; `pf.wins` (career) hides `pf.career-first`; `ev.record-watch` hides `ev.top-score`; `ev.drought-ended` hides `rec.drought-clock` on the same Sunday; `pf.tier-run` at 2× hides `pf.beat-field-streak` for the same run length band. |
| One per family in `top` | the rest go to "More insights" |
| One conditions kind per profile | at most one of `pf.wet-strength`, `pf.weather-steady`, `pf.best-temp`, `pf.tough-days` anywhere on the profile |
| Stats-card overlap (D12) | The profile keeps the Plan 08 Stats card (§3.7), and one fact appears in one place. The card owns its figures; an insight on the profile may not restate one. Resolved per overlap: **Next milestone** vs `pf.sunday-milestone` to-go variant → that variant is home-only (§2.2.3); the crossing variant ("100th Sunday") is news, not on the card, and stays. **Peak rating** vs `pf.rating-high` → the headline states the rise and that it is the current high, never the peak figure (§2.2.1). **Form** (vs usual, last 5 rounds) vs `pf.hot-form` (vs the field's middle score, last 5 Sundays) → different baselines, so not the same fact; the headline and `how` always say "the field's middle score" and never use the words "form", "hot" or "cold", so the two do not read as one number. **Wins / podiums** (career) vs `pf.wins` → the insight only states a first (of year or career) or this year's count, never the career totals. **Floor / ceiling**, **bad-day rate**, **avg percentile** and **rust** have no insight twin (`pf.low-end-rising` is a year-on-year change, `pf.top-of-club` a 12-month placing, `pf.back-strong` one return). A later kind that would restate a card figure is either reworded to the change/news or kept off the profile. |
| One named story per shooter on home | a shooter appears in at most one home card (the kudos strip is separate) |
| Name spread on Sundays | `ev.week-jump` excludes `ev.spotlight` names |
| Roll-ups | on the Sunday and home pages, shooter rows of the same kind anchored to the same Sunday render as one card ("Personal bests today: …", ≤ 5 names, rest in More); the card's key is the roll-up key (§3.1) |
| Silence | a page with nothing that passes shows nothing: no filler, no "not enough data" |

**Rotation (all deterministic, so static until the data changes)**

| Rotation | Rule |
|---|---|
| Phrasing | variant = `hash(key) mod n_templates`: stable for the life of the insight, so no recompute rewords old cards |
| Home hero | top `rank_score` among home candidates with `strength ≥ 1.2`, skipping any kind that was hero in the previous 4 Sundays and any shooter who was hero in the previous 3 (history from `insight_picks`) |
| Fair spotlight ("Shooter to know") | among shooters with a positive person insight anchored to the latest Sunday, the one with the fewest spotlights in the last 26 Sundays; no repeat within 8 Sundays; needs ≥ 3 candidates |
| "New" chip | `first_generation == generation` (so a changed `value_hash` counts as new); never on `pf.digest-line` or the recap |
| "More insights" | everything else for that page and subject, ranked, grouped by family; capped at 30 |

### 3.5 Text templating

- **Templates are code, not data.** Each template is a tuple of clauses of literal text and typed slots: `T(named("New personal best for ", Shooter("s"), ": ", Int("new"), ", beating the ", Int("old"), " from ", MonthYear("old_date"), "."))`.
- **Slot types:** `Shooter` (id → display name), `Int`, `Dec1` (one decimal), `Signed` (+/−), `Pct`, `Date` ("Aug 3"), `MonthYear`, `SundayDate` ("Sunday 9/27"), `Ordinal` ("4th"), `Count` with a singular/plural noun ("1 Sunday / 3 Sundays"), `NameList` (≤ 5 shooters, "A, B and C"), `TrophyName`, `Station`.
- **Output is segments, never HTML:** `[{"t": "text", "v": "New personal best for "}, {"t": "shooter", "id": 182, "v": "Pat K."}, {"t": "num", "v": "46"}, …]`. The frontend renders segments as React text nodes (names become profile links). No `dangerouslySetInnerHTML`; no string concatenation of data into markup. Display names and trophy names are the only data strings and only enter through their slot types.
- **Person forms:** everything a shooter-subject kind renders is written twice with the same slots: third person (name, they/their) and second person (you/your). That covers the headline (`headline` / `headline_you`), the `how` bullets (`how` / `how_you`) and the chart label (`label` / `label_you`, for example "Pat K.'s scores, last 3 months" / "Your scores, last 3 months"). The client shows the `_you` forms only when `getMe() == subject id`; every other viewer sees the third-person forms of the same insights (D11). Multi-name Sunday cards are third person only.
- **Vocabulary (STYLE.md):** "the field's middle score", "usual for a day like this" ("your usual" in the `_you` forms), "skill rating", "Sunday", "targets", "rounds of 40 or better". Numbers match the chart's rounding (1 decimal for averages, whole targets for scores).
- `how` bullets use the same slot system, say what is counted and excluded ("the best round each Sunday", "Sundays with full results", "all round types"), quote the guard ("needs at least 6 wet and 12 dry Sundays"), and stay under ~90 words with the headline.

### 3.6 Chart links (every insight carries one)

#### 3.6.1 Shapes (`chart` jsonb → `InsightChartOut`)

```jsonc
// Explorer link
{"type": "explorer", "spec": QuerySpec, "chart_type": "bar"|"line",
 "highlight": {"dates": ["2026-09-27"]} | {"shooter_ids": [182]} | {"keys": ["wet"]},
 "ref": 40, "compare": QuerySpec | null, "window": {"from": "2026-06-28", "to": "2026-09-27"},
 "label": "Pat K.'s scores, last 3 months", "label_you": "Your scores, last 3 months"}
// Page chart anchor (anchor = the target ChartFrame's urlKey, §3.6.4)
{"type": "page", "route": "/shooters/182", "anchor": "trend",
 "params": {"hl": "2026-09-27", "line": "rolling10"}, "window": {"from": "…", "to": "…"}, "label": "Score history"}
// Extra evidence links (optional, e.g. per-name links on the rain card)
"also": [ …same shapes… ]
```

- The backend stores a `QuerySpec` (C9 model). Spec validity is checked in CI, not at recompute time: a test builds every kind's chart on the fx world and runs `engine._validate` plus `run_query` on it (§5).
- **Always an explicit window.** `window` is never null. An all-time claim writes `from` = the first held Sunday (or the shooter's first round) and `to` = S. This keeps links correct after the time-window work makes "no from/to" mean "last 3 months".
- **Always all round types.** Chart links are built by `features/insights/chartLink.ts` as plain hrefs and never pass through `useRoundTypeLink`, `withRoundTypes` or `useRoundTypeHref`. The target URL carries no `rt`, which the C10 codec reads as `[]` (no filter), so a viewer with a global `rt` lands on the unfiltered chart the insight was computed from. Name links in headlines still use `useRoundTypeLink`.
- Explorer: the frontend serializes the spec with the existing `features/explorer/urlState.ts` codecs (`m, a, g, from, to, st, ga, sh, mr, best, s, c, t, w, p`) plus the new keys in §3.6.3 into `/explorer?…`.
- Page anchor: serialized as `route?{urlKey}.hl=…&{urlKey}.from=…&{urlKey}.to=…#chart-{urlKey}`, namespaced by the target `ChartFrame`'s `urlKey`, so two charts on one page never share a highlight. `ChartFrame` renders `id="chart-{urlKey}"` on its root (Phase 0 T2, §3.9).

#### 3.6.2 Highlighting and the time window

| Concern | Rule |
|---|---|
| What `hl` does | The target chart draws the highlighted points or bars in the accent colour with a larger symbol and a label ("This Sunday", "Run start"), dims the rest to 50%, scrolls the chart into view and focuses it. A range (`hl=d1..d10`) shades the span. `hl` accepts dates, `s:{shooter_id}`, band keys, station numbers, round ids and up to 20 values. |
| `ref` | A dashed horizontal reference line with its label ("40", "Field's middle score = 0", "Typical Sunday"). |
| `cmp` | A second series from the compare spec, styled as the muted "field" series. |
| Evidence window | Each kind's `chart` builder sets `window` to the smallest span that shows the evidence plus context, as in the §2.2 tables: the default recent window [S − 3 months, S] when the evidence fits in it; the run start − 2 Sundays for streaks; [S − 1 y, S] or [S − 2 y, S] for year comparisons; [first round, S] for "first ever" and all-time shooter claims; [first held Sunday, S] for all-time club, year- and band-grouped claims. |
| Past Sundays | The window ends at the anchor Sunday S, not today, so a two-year-old insight shows the chart as it looked then. |
| Default vs link | The link's window overrides the 3-month default (D8). When the user later changes the window so a highlighted point falls outside it, the chart shows a chip "The highlighted Sunday is outside this window · Show it", which restores the link's window. |
| Explainer | Every target chart carries its STYLE.md explainer (D8); the insight's own "How we worked it out" is separate and lives on the card. |

#### 3.6.3 New chart capabilities the v1 kinds need

| Where | Addition | Used by |
|---|---|---|
| Explorer URL + chart | `hl`, `ref`, `cmp` params | most `Ex` links |
| Explorer engine (C9) | metric `difficulty` (event-level, from `event_metrics`); validated like `attendance` (an event total: no shooter, status, gauge, minimum-rounds or best-round filters) | `ev.how-it-played`, `ev.toughest-since`, `cl.rain-scores`, `cl.weather-scoreboard` |
| Explorer engine | agg `p25` ("low end") | `pf.low-end-rising` |
| Explorer engine | filter `min_score` | `pf.high-round-count`, `pf.more-high-rounds` |
| Explorer engine | `ytd=MM-DD` same-date cutoff per year | `cl.year-pace` |
| Profile score history (`trend`) | rolling-10 and rolling-20 lines; "average so far" line; PB line; `hl` ranges | form and streak kinds |
| Profile | finish strip (`finishes`), difficulty × vs-field scatter (`tough-days`), attendance calendar month view (`cal`), trophies `hl` | `pf.podium-run`, `pf.tough-days`, `pf.months-in-row`, trophy kinds |
| Rating history (`rating`) | `hl` | `pf.rating-high` |
| Leaderboards | 12-month rating movers bar (`lb-movers`), board row `hl` (`lb-board`) | `pf.rank-climb`, `lb.most-improved` |
| Race page (`/race`, Plan 09 T6) | `hl` on the existing `race-bars` chart; no new points-race chart | `lb.new-leader`, `lb.title-race`, `lb.biggest-climb` |
| Club | first-round histogram (`first-rounds`); `hl` on `new` | `ev.new-faces`, `cl.newcomers` |
| Results table (`results`), records highest-scores (`rec-highest`) and streaks (`rec-streaks`), stations hit-rate (`hit-rate`) | row `hl` | Sunday, records and station kinds |

Each new page chart is a `ChartFrame` with its own STYLE.md explainer (D8). Class removal (Phase 0 T1) drops `Dim.CLASS`, the explorer `klass` column and the rating-chart class bands; nothing here adds them back.

**Explorer URL keys** (added to `features/explorer/urlState.ts`, `METRICS`, `AGGS` and `AGGREGATED_METRICS`; one owner per wave, §6.2)

| Key | Value | Validation |
|---|---|---|
| `m=difficulty` | metric | event total: rejects `sh`, `st`, `ga`, `mr`, `best`; group-by limited to event, month, year, season, band dims |
| `a=p25` | agg | numeric metrics only |
| `ms` | `min_score`, int 0–50 | score-based metrics only |
| `ytd` | `MM-DD` | only with `g=year` |
| `hl` | comma list (≤ 20) of dates, `s:{id}`, band keys, station numbers, `r:{round_id}`, or a range `a..b` | unknown values ignored |
| `ref` | number | — |
| `cmp` | the compare spec as the same keys prefixed `c.` (`c.m`, `c.a`, `c.g`, `c.sh`, `c.best`, …); window shared with the main spec | same validation as the main spec |

#### 3.6.4 Anchor registry

`frontend/src/features/insights/anchors.ts` exports this list; the backend chart builders import the same ids from `analytics/insights/anchors.py`. A frontend test asserts every anchor the backend can emit (exported by a backend test to `tests/golden/insight_anchors.json`) resolves to a rendered `ChartFrame` with that `id`.

| anchor (urlKey) | route | feature | exists on `main`? | owning task |
|---|---|---|---|---|
| `trend` | `/shooters/:id` | shooters | yes; rolling/PB/average lines are new | Phase 2 T1 (lines) |
| `cal` | `/shooters/:id` | shooters | yes; month view is new | Phase 4 T1 (month view) |
| `learn` | `/shooters/:id` | shooters | yes | — |
| `rating` | `/shooters/:id` | shooters | yes | — |
| `finishes` | `/shooters/:id` | shooters | new | Phase 2 T1 |
| `tough-days` | `/shooters/:id` | shooters | new | Phase 4 T1 |
| `trophies` | `/shooters/:id` | achievements (Plan 10 T7–T8) | Plan 10 | Phase 4 T2 (`hl`) |
| `results` | `/events/:date` | events | Results card has no urlKey today | Phase 0 T2 |
| `new` | `/club` | club | yes | — |
| `first-rounds` | `/club` | club | new | Phase 3 T2 |
| `rec-highest` | `/records` | records | highest-scores table has no urlKey today | Phase 0 T2 |
| `rec-streaks` | `/records` | records | yes | — |
| `lb-board`, `lb-movers` | `/leaderboards` | leaderboards | board has no urlKey; movers is new | Phase 0 T2 (board id), Phase 4 T1 (movers) |
| `race-bars` | `/race` | race | yes | — |
| `hit-rate` | `/stations` | stations (Plan 10) | Plan 10 | Phase 4 T2 |

### 3.7 API

All `/api/insights/*` routes are ETag-eligible GETs under the Plan 06 middleware (keyed on `data_version`). `/api/admin/insights/kinds` is under `/api/admin/`, so under C8 it sends `Cache-Control: no-store` and never gets an ETag.

| Endpoint | Returns | Notes |
|---|---|---|
| `GET /api/insights/shooters/{id}` | `InsightFeedOut` | `pinned` = digest line; `top` 3; `more`; 404 for an unknown shooter |
| `GET /api/insights/sundays/{date}` | `InsightFeedOut` | `conditions` card, `top` 3 (roll-ups applied), `kudos`, `more`. An existing Sunday that is not held (attendance-only) returns an empty feed; 404 only when no `events` row exists for the date |
| `GET /api/insights/home` | `InsightFeedOut` | `pinned` = recap, `hero`, `spotlight`, `top` 4, `kudos` (latest Sunday), `more` |
| `GET /api/insights/club` | `InsightFeedOut` | |
| `GET /api/insights/leaderboards?season=YYYY` | `InsightFeedOut` | current season only in v1; other seasons return an empty feed |
| `GET /api/insights/records` | `InsightFeedOut` | |
| `GET /api/insights/stations` | `InsightFeedOut` | empty while dormant |
| `GET /api/admin/insights/kinds` | `list[InsightKindStatusOut]` | admin only: per kind `count`, `share`, `dormant`, `reason`; for tuning |

**Existing surfaces.**
- Plan 06 `GET /api/shooters/{id}/insights` and the Plan 08 profile `InsightsCard` (floor/ceiling, bad-day rate, form, wins/podiums, avg percentile, peak rating, rust, next milestone) **stay** as neutral profile stats (D12). Neither is deleted and the endpoint's response is unchanged. The new insights section is mounted right after `ProfileHero` (`placement: 'top'`, §3.9) and coexists with the card, which keeps its current position; the stats-card overlap rule (§3.4) keeps any card fact from being repeated by an insight. To avoid two things called "Insights" on one profile, Phase 1c T3 changes only the card's visible title from "Insights" to "Stats" (component, hook and route names unchanged); see §7. The card is outside the insights pipeline, so the §4 lints (e.g. "bad" in "Bad-day rate") do not apply to it.
- The Sunday page `NotablesCard` loses upsets (D9; removed by the good-vibes removal task, not by this plan). Its PB and first-timer rows are removed by Phase 3 T3, the task that ships `ev.new-faces` on the Sunday page; `pf.pb` already uses the same C12 `personal_bests` helper, so the counts agree while both exist.

Response models (feature-prefixed per Plan 11 D8):

```python
class InsightSegmentOut(BaseModel): t: Literal["text", "shooter", "num", "date", "trophy", "station"]; v: str; id: int | None = None
class InsightWindowOut(BaseModel): from_: date = Field(alias="from"); to: date
class InsightChartOut(BaseModel): type: Literal["explorer", "page"]; label: str; label_you: str | None = None
    spec: QuerySpec | None; chart_type: str | None; route: str | None; anchor: str | None; params: dict[str, str] = {}
    highlight: dict[str, list[str | int]] = {}; ref: float | None = None; compare: QuerySpec | None = None
    window: InsightWindowOut; also: list["InsightChartOut"] = []
class InsightOut(BaseModel): key: str; kind: str; family: str; subject_type: str; subject_id: str; anchor_date: date | None
    polarity: Literal["positive", "neutral", "field_negative", "mixed"]; kudos: bool; is_new: bool
    headline: list[InsightSegmentOut]; headline_you: list[InsightSegmentOut] | None; headline_text: str
    how: list[list[InsightSegmentOut]]; how_you: list[list[InsightSegmentOut]] | None
    chart: InsightChartOut; rank_score: float
class InsightKudosOut(BaseModel): shooter_id: int; display_name: str; insight: InsightOut   # one chip per shooter, their top kudos row
class InsightFeedOut(BaseModel): data_version: int; as_of: date; pinned: InsightOut | None; hero: InsightOut | None
    spotlight: InsightOut | None; conditions: InsightOut | None; top: list[InsightOut]; kudos: list[InsightKudosOut]
    more: list[InsightOut]; n_more: int
```

`headline_text` is the plain-text join (for share images, aria labels and tests). `kudos` is the full ranked list (not capped); the 10-chip cap and "and N more" are applied by `KudosStrip` (D10).

### 3.8 UI (`src/features/insights/`)

| Component | Behaviour |
|---|---|
| `InsightCard` | Family icon, headline (segments; names link through `useRoundTypeLink`), optional "New" chip, and two actions: **See the chart** (a plain href from `chartLink.ts`, §3.6.1) and **How we worked it out** (toggles the explainer panel). Card body ≤ 3 lines at 390 px, except the recap (below). |
| `InsightExplainer` | Uses `ExplainerPanel` (What this shows / How to read it / How it's worked out): "What this says" = headline, "How we worked it out" = `how` bullets (`how_you` for Me), plus "Numbers used" (sample sizes from params) and "All round types". Inline expand on desktop; bottom `Sheet` on mobile. If the explainer work has not landed, Phase 1c T2 ships `ExplainerPanel` in `components/explainer/` with that three-part shape for the explainer work to adopt (§6.1). |
| `KudosStrip` | "This week's kudos" (home) / "Kudos" (Sunday page): one chip per shooter with their top kudos insight as a short label ("Pat K. · 4 above own average"), tap → that card in a `Sheet`. At most 10 chips; beyond that, a final "and N more" chip opens a `Sheet` listing every kudos chip for that Sunday (D10). Horizontal scroll inside the strip only; the page never scrolls sideways at 390 px. Hidden when empty. |
| `MoreInsights` | "More insights (N)" button → `Sheet` on mobile, inline expand on desktop; grouped by family; lazy-loads nothing (already in the feed). |
| `InsightHero` | Home only: larger card for `hero`, plus the "Shooter to know" spotlight line. |
| `RecapCard` | Home only: the recap, clamped to 3 lines with "Show all"; each slot's clause links its own chart. |
| `InsightsSection` | Fetches the feed for a page and lays out the pieces. Mounted only through the extension points in §3.9; never edits a page file directly. |

**Placement** (all through §3.9; `top` = the new `placement: 'top'` position)

| Page | Mobile (< 1024 px) | Desktop (≥ 1024 px) |
|---|---|---|
| Home (`homeWidget`, `slot: 'hero'`) | recap card, hero, kudos strip, 4 cards stacked, More; above `LatestEventCard` | recap + hero side by side, kudos strip full width, 4 cards in a 2 × 2 grid, More |
| Sunday (`eventSection`, `placement: 'top'`) | conditions card and 3 cards after the stats row, before the Results card; kudos strip; More | conditions card + 3 cards in a row, same position; kudos strip; More |
| Profile (`profileSection`, `placement: 'top'`) | digest line and 3 cards right after `ProfileHero`, More; the Stats card (Plan 08) stays where it is today | same, cards in a 3-column row |
| Club, Leaderboards, Records, Stations (`pageTop`) | 2–3 cards stacked at the top of the page, More | cards in a row at the top, More |

### 3.9 Extension points and file ownership (C10 amendment; resolves the placement conflict)

On `main`, `ProfilePage` renders `ProfileSections` last, `EventDetailView` renders `EventSections` after Results, Station hits, Weather, VsPrev and Notables, and `HomePage` renders `WidgetSlot slot="main"` after `LatestEventCard` and `ClubPulse`. `order` cannot lift a section above those fixed blocks, and C10 lets only Plan 08 edit `features/home|events|shooters/`. The club, leaderboards, records and stations pages have no extension glob.

**Plan 12 Phase 0 T2 ("extension points", a Plan 08 follow-up)** is the only insights task that edits `features/home`, `features/events`, `features/shooters`, `features/club`, `features/leaderboards`, `features/records` (and `features/stations` if it exists by then). It:
- Adds `placement?: 'top' | 'bottom'` (default `'bottom'`) to `ProfileSection` and `EventSection`, and `slot: 'hero'` to `HomeWidget['slot']`.
- Renders `top` profile sections right after `ProfileHero`, `top` event sections after the event stats row and before the Results card, and `hero` widgets above `LatestEventCard`. Existing sections keep `bottom` and do not move.
- Adds a fourth glob, `pageTop`: `src/features/<name>/pageTop.tsx` exports `pageTop: {id, page: 'club' | 'leaderboards' | 'records' | 'stations', order, Component}`, collected in `src/components/layout/pageTop.ts`, and inserts one `<PageTopSlot page="…"/>` at the top of `ClubPage`, `LeaderboardsPage` and `RecordsPage` (Plan 10's `StationsPage` adds its own line when it lands, or Phase 4 T2 does).
- Adds `id="chart-{urlKey}"` to `ChartFrame` (a `components/charts/` edit, allowed here only) and urlKeys `results` (Results card), `rec-highest` (records highest-scores table) and `lb-board` (leaderboard board).
- Extends each registry test (`sections.test.ts`, `widgets.test.ts`, new `pageTop.test.ts`) for placement and slot.

Later insights tasks touch these features only through `src/features/insights/{profileSection,eventSection,homeWidget,pageTop}.tsx`, with three named exceptions recorded in §6.3: Phase 1c T3 (the Plan 08 card's visible title "Insights" → "Stats", and its test; nothing else in that card changes), Phase 2 T1 / Phase 4 T1 (new profile, leaderboards and club charts listed in §3.6.4) and Phase 3 T3 (Notables PB and first-timer rows).

---

## 4. Guardrails

### 4.1 Positivity by construction (D1)

| Layer | Mechanism |
|---|---|
| Registry | `subject = shooter` kinds must be `positive` or `neutral`; `field_negative` kinds have no named clauses; in `mixed` kinds only name-free `field` clauses may be negative (import-time validation, §3.3). |
| Generators | Return a Fact only when the favourable condition holds; no negative variant exists for named kinds. Finish/score slots in neutral kinds are dropped when unflattering (`pf.digest-line` finish only in the top half; `pf.back-strong` score only if ≥ their average). |
| Database | `CHECK (polarity <> 'field_negative' OR cardinality(named_shooter_ids) = 0)`; `polarity` in the four allowed values. |
| Tests | (a) **Worse-at-everything test:** a synthetic shooter who is below the field, below their own history and falling on every dimension is inserted into the fx world. The only rows naming them may come from the neutral allowlist `{pf.digest-line, pf.back-strong, ev.second-visit, ev.new-faces (welcome clause), pf.sunday-milestone, pf.shooter-anniversary, pf.attendance-year, pf.attendance-streak, pf.months-in-row}`, and those rows' params may contain no finish, score or residual below its show-guard (digest-line: no finish, no residual; back-strong: no score; new-faces: welcome only, no "strong start"; anniversary: no best). (b) **Negative-word lint** on every `named` clause of every template, every `how`/`how_you` bullet and every chart label: `worst, worse, slump, drop, dropped, fell, lost, below, behind, struggl, bad, poor, off form, decline, last place`. ("Off days getting better" is allowed as a whole phrase in `pf.low-end-rising` only.) `field` clauses are exempt, since club or field negatives are allowed. |

### 4.2 Language lints (run on every template variant, every `how`/`how_you` bullet, every `label`/`label_you` and `also` label, and the text segments of every rendered headline in the fx golden run)

Rendered headlines are linted on their `text` segments only, so a display name (a shooter surnamed "He") never trips a lint.

| Lint | Rule |
|---|---|
| No person-vs-person (D9) | `\b(upsets?\|giant[- ]?killer\|odds\|favou?rites?\|rivals?\|rivalry\|head[- ]to[- ]head)\b` (case-insensitive) → fail. Names are slots, not text, so the comparison itself is caught structurally: in a `named` clause, a second `Shooter`/`NameList` slot is allowed only in the list shapes "A and B both …", "A, B and C" or a roll-up, and the literal text between two name slots may not contain "ahead", "behind", "lead", "beat", "over" or "than" (import-time registry validation, §3.3). "Beating the 44 from Aug 2024" (`pf.pb`) passes: it compares a shooter with their own history. |
| Pronouns (D2) | case-insensitive `\b(he\|she\|his\|her\|hers\|him\|himself\|herself)\b` → fail |
| Class (D3) | `\bclass(es)?\b` → fail |
| Sunday (D7) | `\bevents?\b` → fail |
| Jargon (STYLE) | `residual, percentile, median, stdev, standard deviation, z-score, significant, correlation, regression, mu, sigma, expected` → fail |
| Second person | every `_you` form must contain "you"/"your"; the third-person forms must not |

### 4.3 Minimum-sample guards

| Guard | Default (a kind may be stricter; values live in `Kind.guard` and are quoted by the explainer) |
|---|---|
| Subject eligibility | evergreen profile kinds: shooter active at `as_of` (≥ 5 rounds, 1 in 364 days), and guests with < 6 rounds are excluded. Sunday welcome kinds (`ev.new-faces`, `ev.second-visit`, `pf.back-strong`) name guests by design; the guest rule does not apply to them. |
| Prior history | ≥ 10–20 prior rounds for "own usual" kinds; the C12 rule (≥ 5 prior) for `pf.pb`; ≥ 12 for the other PB-type kinds |
| Field size | ≥ 15 shooters for finish-based kinds (podium, top third, close finish) |
| Weather splits | ≥ 6 wet / 12 dry (profile), 4 / 8 (Sunday names), band ≥ 6 rounds; shuffle test 90–95% with a seeded RNG |
| Noise | differences must be ≥ 2× their standard error where the table says so |
| Stations | ≥ 8 station Sundays, ≥ 30 entries per station, ≥ 4 Sundays per shooter at a station |

### 4.4 No-leak

- Every anchored kind evaluates on frames sliced to `event_date ≤ S`, with baselines from `< S`. The skill model's `expected` and `mu_before` are already pre-event (C7). Rating ranks use `rating_history` rows ≤ S.
- Consequence: an insight dated S does not change when later Sundays are uploaded (only its recency and the "New" chip do), **unless** the skill model is recalibrated (`recompute {"recalibrate": true}` rewrites `expected`, `residual`, `difficulty` and `rating_history` for all history) or weather for S is backfilled (weather kinds for S appear or change on the weather-sync recompute, §3.2).
- Evergreen kinds are computed as of the latest held Sunday and make no claim about earlier dates.

### 4.5 Dormant kinds switch on automatically

| Kind group | `requires` | Turns on when |
|---|---|---|
| Stations (`st.*`, `pf.station-*`, `ev.station-*`) | `station_sundays ≥ 8` and ≥ 30 entries per station | enough station sheets are uploaded; the next recompute emits them |
| Trophies (`pf.trophy-*`, `pf.next-trophy`, `ev.trophy-haul`, `cl.trophy-*`, `home.year-first-trophy`) | `trophy_awards ≥ 1` | `achievements_awarded` has rows |

No code change or flag is needed. `GET /api/admin/insights/kinds` shows each dormant kind with its reason. A test flips the readiness inputs on the fx world (adds 8 synthetic station Sundays / awards) and asserts the kinds start emitting.

---

## 5. Testing strategy

| Layer | Test | Detail |
|---|---|---|
| Weather fixture | `tests/fixtures/event_weather_2026-09-27.json` | the `event_weather` rows for the 310 Sundays exported once from the dev stack. `fx_engine` (tests/conftest.py) loads it before `run_pipeline`, so weather bands, difficulty-by-band and the weather kinds are exercised. Phase 1a T1 owns the conftest edit. |
| Golden counts | `tests/golden/insights_counts.json` on the fx world (committed scores + stations + the weather fixture) | per kind: profile count of 84 active shooters, % of Sundays firing over the last 145, total rows. Values are recorded once from the fx world; the spot-checked kinds must sit within ±2 shooters / ±3 points of CATALOG §2 and §6.2 (differences explained in the PR; `pf.pb` is re-recorded under the C12 rule). Coverage: ≤ 9 of 84 active shooters with no profile insight. |
| Per kind | one unit test module per registry module | hand-built frames for: fires at each variant's guard with `strength ≥ 1`, silent just below it, the right numbers in `params`, both person forms render (headline, how, label), the chart builder returns a spec/anchor and the right explicit window. |
| Chart specs | CI only | every kind's chart built on the fx world passes `engine._validate` and `run_query`; every page anchor is in the anchor registry (§3.6.4). |
| Proof | chart-proof test | for every Fact on the fx world, run the stored spec through `run_query` with `round_types=[]` (or call the endpoint that feeds the anchored chart) and apply the kind's `proof` checks: each headline param is a `Cell` (one row's value), `Sum`/`Mean` over the `hl` rows, `CountRows` of `hl` rows, `RunLength` of consecutive `hl` rows, `RankOf` the `hl` row, `DateOf` a row, `Share` of rows passing a threshold, or `NA(reason)` (for example a sample size quoted only in "how"). Values match within display rounding. |
| No-leak (property) | Hypothesis over fx Sundays S, `skill_params` pinned from the full-data run | compute anchored insights with the full data and with every Sunday after S removed; the rows anchored at S are identical except `rank_score`, `generation` and `first_generation`. |
| Idempotence | run `s60` twice, then run a weather-only recompute | identical `key`, `headline`, `headline_you`, `template_id`, `params` and `chart`; `first_generation` carried; a changed upload marks only new keys or changed `value_hash` "New". |
| Ranking | selection unit tests | one-per-family, home slots, one conditions kind per profile, supersedes, roll-ups (and roll-up keys), name spread, hero and spotlight rotation over a scripted 10-Sunday history with recency relative to the pick Sunday, per-page expiry (`pf.pb` evergreen profile row vs home after 3 Sundays), kudos anchor for `lb.most-improved`, silence when nothing passes, stats-card overlap (no `pf.sunday-milestone` to-go row on the profile; `pf.rating-high` headline carries no peak figure). |
| Guardrails | §4.1–4.2 tests | worse-at-everything with the allowlist, negative-word lint on named clauses, per-clause polarity validation, pronoun/class/event/jargon/D9 lints on text segments and labels, a D9 fixture template ("A beat B") fails registry load, DB CHECK violation raises. |
| Registry | import-time validation | a deliberately bad Kind in a test package fails to load (field clause with a name, missing `proof`, missing `home_slot`). |
| API | integration on `fx_viewer_client` | each endpoint's shape; empty feed for an attendance-only Sunday, 404 for a date with no event; ETag/304 on viewer routes; admin endpoint needs admin and sends `no-store` with no ETag. |
| Frontend | Vitest + MSW | `InsightCard` segments render names as links and never as HTML; `_you` forms only for Me; explainer panel opens inline/in a Sheet; `KudosStrip` hidden when empty, shows exactly 10 chips plus "and 5 more" for 15 kudos (and no "more" chip for 10), and "and 5 more" opens a Sheet with all 15; a non-Me viewer sees a shooter's profile insights and digest line in third person; `chartLink.ts` produces the expected `/explorer?…&hl=` and page URLs with an explicit window; with a global `rt=super_sporting`, the chart link has no `rt`. |
| Chart targets | Vitest | `hl`, `ref`, `cmp` parse and style the right points; the out-of-window chip appears and restores the window; every registry anchor resolves to `id="chart-{urlKey}"`; placement `top` renders above the fixed blocks. |
| E2E | Playwright (fx world) | home shows recap, hero, kudos and 4 cards; a profile card → "See the chart" lands on the chart with the highlight visible and the link's window; "How we worked it out" opens; no horizontal scroll at 390 px on home, Sunday and profile. `compose.test.yaml` keeps `WEATHER_ENABLED=false` and the C10 weather empty-state assertion stands, so e2e does not assert a wet-day card (the weather kinds are covered by the backend golden run on the fixture). |
| Performance | integration, `slow` marker | `s60` on the fx world finishes within 2× the time recorded in Phase 1a. |

---

## 6. Rollout

Insights is **Plan 12** (Wave 6, after Plan 11). Task ids below are Plan 12's.

### 6.1 Dependencies

| Dependency | Why | Owner |
|---|---|---|
| Class removal | drops `Dim.CLASS`, `klass`, `analytics/classes.py`, `GET /api/classes`, the rating-chart class bands and any class-based trophy | Plan 12 Phase 0 T1 (no separate spec exists; the task is scoped by this list and the D3 lint) |
| Extension points, anchor ids | §3.9 | Plan 12 Phase 0 T2 |
| Explainer work (`ExplainerPanel`, per-chart explainers) | "How we worked it out" uses the panel; every target chart needs its explainer (D8) | the separate explainer spec/plan if it lands first; otherwise Phase 1c T2 ships a minimal `ExplainerPanel` and Phases 2–4 add explainers to every new chart they create. Insights never blocks on it. |
| Time-window work (3-month default + presets) | the out-of-window chip | the separate time-window plan. Links write explicit windows (§3.6.1), so they are correct before and after it lands; the chip ships with whichever lands second. |
| Plan 09 leaderboards, records and race pages; Plan 10 stations and achievements UI | chart targets for `lb.*`, `rec.*`, `st.*`, trophy kinds | Phases 3–4 |
| Plan 11 (Wave 5) | T2 turnout rules must match `cl.rain-turnout`; T4 Year in Review becomes the richer target for `pf.year-wrapped`/`cl.year-wrap`; T5 share images can wrap `InsightCard` later. Insights never use predictions (T1) or rivals (T3). | Insights start after Plan 11 lands, so home and profile layouts settle once |

### 6.2 Phased build (each phase is one stacked PR stack; ≲ 10 agents per workflow, one stack at a time)

Shared-file rule: in any wave, each of `explorer/spec.py`, `explorer/engine.py`, `components/charts/explore.ts`, `features/explorer/urlState.ts`, `tests/conftest.py`, `analytics/insights/registry.py` and each `features/<page>/` directory has exactly one owning task. A migration task never shares a wave (C4).

| Phase | Task | Owns (files) | Kinds |
|---|---|---|---|
| **0** (T1 wave, then T2 wave) | T1 class removal | `explorer/spec.py`, `explorer/engine.py`, `analytics/classes.py` (delete), `api/routes/classes.py` (delete), rating-chart class bands, class trophies | — |
| | T2 extension points (§3.9) | `features/{home,events,shooters,club,leaderboards,records}/` registry and page files, `components/charts/ChartFrame.tsx`, `components/layout/pageTop.ts` | — |
| **1a** backend core | T1 migration + weather fixture | `migrations/versions/<next>_insights.py`, `models/`, `tests/conftest.py`, `tests/fixtures/event_weather_*.json` (own wave) | — |
| | T2 registry, `Kind`, templating, lints, validation | `analytics/insights/{registry,templates,lints}.py` | — |
| | T3 s60 step, ranking, selection, clamp, benchmark | `analytics/steps/s60_insights.py`, `analytics/insights/{rank,select}.py` | `pf.pb`, `ev.spotlight`, `pf.digest-line` |
| **1b** links + API | T1 Explorer additions (`difficulty`, `hl`/`ref`/`cmp` URL keys) | `explorer/spec.py`, `explorer/engine.py`, `features/explorer/urlState.ts`, `components/charts/explore.ts` | — |
| | T2 chart-link builder, anchor registry, proof harness | `analytics/insights/{charts,anchors,proof}.py` | — |
| | T3 API (shooter, Sunday, home, admin kinds) | `api/routes/insights.py`, `api/schemas/insights.py` | — |
| **1c** UI | T1 `InsightCard`, `chartLink.ts`, segments | `features/insights/components/`, `features/insights/chartLink.ts` | — |
| | T2 `InsightExplainer`, `KudosStrip`, `MoreInsights`, `RecapCard` (+ minimal `ExplainerPanel` if needed) | `features/insights/components/`, `components/explainer/` | — |
| | T3 mounts + Stats card title | `features/insights/{profileSection,eventSection,homeWidget}.tsx`; `features/shooters/components/InsightsCard.tsx` and its test (visible title "Insights" → "Stats" only, named exception). The card, `useShooterInsights` and the Plan 06 `GET /api/shooters/{id}/insights` route stay (D12) | — |
| **1d** rest of the first 15 | T1–T3, 4 kinds each | `analytics/insights/{form,streaks,milestones,conditions,sunday}.py` split by module | `pf.tied-best`, `pf.beat-field-streak`, `pf.above-own-avg-streak`, `pf.hot-form`, `pf.sunday-milestone`, `pf.wins`, `pf.back-strong`, `pf.wet-strength`, `pf.weather-steady`, `ev.rain-day`, `ev.how-it-played`, `ev.close-finish` |
| **2** profile kudos and form | T1 profile charts (rolling lines, average-so-far, PB line, finish strip) | `features/shooters/components/ProfileCharts.tsx` (named exception) | — |
| | T2 Explorer `p25`, `ms` | explorer files (sole owner this wave) | — |
| | T3–T6 kinds, 5 each | registry modules | the 20 in the Phase 2 list below |
| **3** Sunday, home, club | T1 hero/spotlight rotation, `insight_picks`, recap, club API | `analytics/insights/select.py`, `api/routes/insights.py` | — |
| | T2 first-round histogram, `ytd` | `features/club/` chart (named exception), explorer files | — |
| | T3 Sunday-page kinds + Notables PB/first-timer removal | `features/events/components/NotablesCard.tsx` (named exception), `analytics/insights/sunday.py` | — |
| | T4–T6 kinds | registry modules | the 21 in the Phase 3 list below |
| **4** attendance, conditions, season, dormant | T1 attendance month view, tough-days scatter, movers bar | `features/shooters/`, `features/leaderboards/` chart files (named exceptions) | — |
| | T2 leaderboards/records/stations APIs + `pageTop` mounts, trophies/stations `hl`, dormant readiness | `features/insights/pageTop.tsx`, `api/routes/insights.py` | — |
| | T3–T5 kinds | registry modules | the 18 in the Phase 4 list below |

| Phase | Kinds | n |
|---|---|---|
| 1a + 1d | `pf.pb`, `ev.spotlight`, `pf.digest-line`, `pf.tied-best`, `pf.beat-field-streak`, `pf.above-own-avg-streak`, `pf.hot-form`, `pf.sunday-milestone`, `pf.wins`, `pf.back-strong`, `pf.wet-strength`, `pf.weather-steady`, `ev.rain-day`, `ev.how-it-played`, `ev.close-finish` | 15 |
| 2 | `pf.three-rising`, `pf.beat-own-usual`, `pf.tier-run`, `pf.best-stretch`, `pf.average-milestone`, `pf.first-tier`, `pf.first-since`, `pf.career-first`, `pf.high-round-count`, `pf.more-high-rounds`, `pf.low-end-rising`, `pf.podium-run`, `pf.up-on-usual`, `pf.year-up`, `pf.years-up-run`, `pf.gaining-on-field`, `pf.rating-high`, `pf.learning-curve`, `pf.season-best`, `pf.best-day-vs-field` | 20 |
| 3 | `ev.toughest-since`, `ev.week-jump`, `ev.record-watch`, `ev.top-score`, `ev.new-faces`, `ev.second-visit`, `home.sunday-recap`, `rec.drought-clock`, `ev.drought-ended`, `cl.rain-turnout`, `cl.rain-scores`, `cl.weather-scoreboard`, `cl.turnout-trend`, `cl.newcomers`, `cl.originals`, `cl.year-wrap`, `cl.year-pace`, `cl.club-one-shooter`, `pf.charter-shooter`, `pf.shooter-anniversary`, `pf.targets-milestone` | 21 |
| 4 | `pf.attendance-year`, `pf.attendance-streak`, `pf.months-in-row`, `pf.year-wrapped`, `pf.best-temp`, `pf.tough-days`, `pf.top-of-club`, `pf.rank-climb`, `lb.new-leader`, `lb.title-race`, `lb.biggest-climb`, `lb.most-improved`, `rec.perfect-rarity`, `rec.streak-chase`, `st.hardest-easiest`, `pf.station-best`, `pf.trophy-rare`, `pf.next-trophy` | 18 |
| Later | the §2.3 list, cheapest first (`ev.tag-chips`, treats, round-2 profile kinds) | — |

15 + 20 + 21 + 18 = 74.

### 6.3 Contract changes (applied to the master plan by Phase 0 T2, in the same PR)

| Clause | Edit |
|---|---|
| C4 | Append: "`<next>_insights` (Plan 12 Phase 1a T1) adds `insights` and `insight_picks`." The number is fixed when the plan is written. |
| C6 | Step orders: add "`60 insights` (Plan 12)". Replace "Classes, leaderboards, records etc. are computed on demand (cached by `data_version`), not stored" with "Leaderboards, records etc. are computed on demand (cached by `data_version`), not stored; insights are the exception and are stored by step 60 (static until the next pipeline run)". |
| C7 | Remove the rating classes (Phase 0 T1). |
| C8 | Viewer: add the seven `GET /api/insights/*` routes (`GET /api/shooters/{id}/insights` stays, D12); remove `GET /api/classes` (Phase 0 T1). Admin: add `GET /api/admin/insights/kinds`. |
| C9 | Remove `Dim.CLASS`; add metric `difficulty`, agg `p25`, filter `min_score`, `ytd` (§3.6.3). |
| C10 | Extension points: add `placement` to `ProfileSection`/`EventSection`, `slot: 'hero'` to `HomeWidget`, the `pageTop` glob, and `ChartFrame`'s `id="chart-{urlKey}"`. Ownership: "Plan 12 Phase 0 T1 may edit those features only to remove class UI; Plan 12 Phase 0 T2 may edit `features/home|events|shooters|club|leaderboards|records/` to add these; Plan 12 Phase 1c T3, Phase 2 T1, Phase 3 T2–T3 and Phase 4 T1 may make the edits named in the insights spec §3.9." Links: "Insight chart links are plain hrefs with an explicit window and no `rt`; they do not use `useRoundTypeLink`." |

---

## 7. Questions

### Resolved (owner, 2026-09-29, binding)

1. **Kudos strip scope → D10.** Cap at 10 chips plus an "and N more" chip that opens the full list (§3.4, §3.7, §3.8, §5).
2. **Profile visibility → D11.** Every logged-in viewer sees every profile's insights, including `pf.digest-line`, as specified; only the `_you` wording is limited to the Me profile (§3.4, §3.5, §5).
3. **Existing Plan 08 profile stats → D12.** Floor/ceiling, bad-day rate, form (hot/cold) and rust ("after 3+ weeks off", 28-day gap) stay as neutral profile stats: they describe one shooter, not person-vs-person. The card and `GET /api/shooters/{id}/insights` are not retired; the insights section coexists above it, and the stats-card overlap rule keeps a card fact from appearing twice (§3.4, §3.7, §6.2).

### Still open

1. **Stats card title.** The spec renames only the Plan 08 card's visible title from "Insights" to "Stats" (Phase 1c T3) so the profile does not show two things called "Insights". Confirm the word, or keep "Insights" on the card and give the new section a different heading instead.

---

## 8. Critique resolution

Findings from `.superpowers/sdd/insights/spec-critique.md` (3 Critical, 16 Important, 14 Minor).

| Finding | Change |
|---|---|
| C1 placement vs C10 | New §3.9: Phase 0 T2 adds `placement: 'top'`, `slot: 'hero'`, a `pageTop` glob for club/leaderboards/records/stations, and `ChartFrame` ids; §3.8 placement rewritten to use them; C10 amendment in §6.3. *Updated after D12:* the old card is kept, so the name clash is resolved by retitling it "Stats" (visible title only, Phase 1c T3; §7 still open). |
| C2 mixed field/named cards | Per-clause polarity and a `mixed` polarity (§3.3, §3.1 CHECK, §4.1); `ev.rain-day` and `home.sunday-recap` are `mixed`; `rec.drought-clock` split into a name-free clock and positive `ev.drought-ended` (v1 is now 74); lints run on named clauses. |
| C3 strength < 1 | Every listed variant given its own strength (fixed 1.5/2 or a variant divisor) in §2.2; undefined "by step/level/thousands/years" and `pf.sunday-milestone` given numbers; runtime assert replaced by per-kind guard-edge tests plus a logged clamp; s60 never raises (§3.2, §3.3). |
| I1 phrasing keyed on generation | `variant = hash(key) mod n` (§3.4); idempotence test checks `headline`, `template_id` and a weather-only recompute (§5). |
| I2 page guards and expiry | Per-Fact `pages`, per-page `expires` jsonb, and an evergreen `profile` row for the nine kinds with separate P guards (§3.1); selection tests per page (§5). |
| I3 proof test | `Kind.proof` with typed `ProofCheck`s (cell, sum, mean, count, run length, rank, date, share, n/a) (§3.3, §5). |
| I4 `rt` and default window | Links always carry an explicit window and no `rt`, and bypass `useRoundTypeLink` (§3.6.1); Vitest with a global `rt`; proof runs with `round_types=[]` (§5). |
| I5 invalid Explorer specs | `cl.originals` → `rounds/count/year`; `cl.year-wrap`/`cl.year-pace` → `rounds/count/year` with "rounds" defined; `cl.club-one-shooter` windowed and one population; `ev.rain-day` names `to=S − 1 d`; `best=true` on best-round kinds; `pf.station-best` compare spec written out; CI spec-validation test, no recompute-time validation. |
| I6 page anchors | Anchors use real urlKeys; anchor registry §3.6.4 with owners; `ChartFrame` `id`; `lb.*` link the existing `/race` `race-bars`; resolution test. |
| I7 `pf.sunday-milestone` data | Count is `shooter_profiles.n_events`; parenthetical removed; anniversaries use C4 `left_censored` (§2.1, §2.2.3). |
| I8 PB/notables/InsightsCard overlap | `pf.pb` uses the C12 `personal_bests` helper (≥ 5 prior); Phase 3 T3 removes Notables PB and first-timer rows. *Updated after D12:* the Plan 06/08 `InsightsCard` and its endpoint are kept as neutral stats (not retired); overlap with insight kinds is handled by the stats-card overlap rule (§3.4, §3.7). |
| I9 worse-at-everything | Test now uses a neutral-kind allowlist and checks those rows' params (§4.1). |
| I10 guest exclusion | Limited to evergreen profile kinds; welcome kinds name guests (§4.3). |
| I11 family and home slot | §2.2.8 maps every kind to a family and home slot; `Kind`/row fields added; kudos anchor for `lb.*` K kinds defined (§3.4). |
| I12 prerequisites | Class removal and extension points are Phase 0 tasks; explainer and time-window work named with non-blocking fallbacks (§6.1). |
| I13 phase size | Split into 0, 1a–1d, 2, 3, 4 with task tables, file ownership and a one-owner-per-shared-file rule (§6.2). |
| I14 contract amendments | §6.3 lists C4, C6, C7, C8, C9 and C10 edits; migration number fixed at plan time (§3.1). |
| I15 recalibration and late weather | No-leak claim qualified (§4.4); `skill_params` pinned in the property test (§5); late weather stated in §3.2. |
| I16 no weather in fx | Committed `event_weather` fixture loaded in `fx_engine` (§5); e2e drops the wet-day card and keeps the C10 weather empty-state rule. |
| M1 `Kind` won't compile | `kw_only=True`, defaults last, one `Polarity` enum matching the DB (§3.3). |
| M2 person forms | `how_you` and `label_you` added (§3.1, §3.5, §3.6.1); lints cover them (§4.2). |
| M3 `ev.week-jump` sample | Rewritten to name only the new score; the earlier score and the jump size are never shown. |
| M4 API notes | Admin route exempted from ETag; empty feed for an attendance-only Sunday, 404 only for no event (§3.7). |
| M5 ranking inputs | Strengths given numbers; rarity denominators defined; recency relative to the pick Sunday (§3.4). |
| M6 Explorer URL keys | URL-key table with validation, incl. `difficulty` on the event-total path and `cmp` as `c.`-prefixed keys (§3.6.3); `t, w, p` added to the codec list. |
| M7 `T` two meanings | First-tier level renamed `L`. |
| M8 30 s budget | Benchmarked in Phase 1a; test asserts 2× the recorded time under `slow` (§3.2, §5). |
| M9 pronoun lint on names | Lints run on text segments only (§4.2). |
| M10 "Vs expected" | Label now "Vs usual for a day like this" / "Vs your usual"; "expected" added to the jargon list; lints extended to labels and `also` labels. |
| M11 key / "New" gaps | `value_hash` for evergreen "New"; roll-up key defined (§3.1, §3.4). |
| M12 recap vs card length | Recap exempted; 3-line clamp with "Show all" (`RecapCard`, §3.8). |
| M13 "active" population | Active judged as of S (§2.1); `cl.club-one-shooter` uses one windowed population in text and chart. |
| M14 conditions card | Now says "wet in v1; cold and windy when those kinds ship" (§3.4). |

User decisions re-checked: no gendered pronoun in any sample or template (D2 lint); no class kind or class wording outside D3 and the class-removal task; every named clause is positive or neutral; every kind has a chart link and a "how".
