# Sunday Clays: Thrown-out stations — Design Spec

> Date: 2026-10-25 · Status: draft for owner review · Base: `main` @ `79ee0d8` · Migration: `0010` (latest is `0009_response_cache`) · Appendix: `2026-10-25-dropped-stations-inventory.md` (every consumer, file:line, class) · Implementation plan: `docs/superpowers/plans/2026-10-25-dropped-stations.md` (written after approval)

Some Sundays a station gets **thrown out**. On 2026-10-25 a trap at Station 11 began breaking targets before they were thrown, so the station was dropped and **every shooter was credited a perfect 7/7 on it**, including the squads that had already shot it. The official score (say 43/50) includes those free targets.

Today the site treats that free station as real shooting. It says 100% of shooters cleaned Station 11, calls it the easiest station, and lets the free 7 lift everyone's averages, PBs, hit rates and trends. This feature detects a thrown-out station on its own, keeps the official results counting, marks them with a **\***, and keeps the free targets out of every statistic. Every explainer says so in the places where it applies.

---

## 1. Goals, non-goals, anti-goals

**Goals**

1. **Auto-detect.** A station is thrown out when *every* station-sheet entry that Sunday has hits equal to that station's target count. Admins can force it on or off.
2. **Official results still count, with a \*.** The Sunday's own results, placings, winners, race points and standings count. So do attendance, Sundays, rounds, streaks of Sundays, and cumulative totals such as clays broken and its milestones and trophies. Wherever such a score is shown it carries a \* and a short explanation.
3. **Statistics leave them out.** Rounds on such a Sunday are excluded from every score statistic: averages, medians across Sundays, bests, PBs, records, distributions, trends, difficulty, rating and skill, predictions, weather effects, score-based trophies and insights, and Explore score metrics.
4. **The station itself leaves station stats.** The thrown-out station's hits are excluded from every station statistic: difficulty, hit rates, clean rates, leaders, heatmaps, wind and eras, station trophies, station insights and recap station lines.
5. **Disclosure where it applies.** Every "what this shows / how it's computed" explainer whose numbers leave these out says so in plain words. Every place that counts them shows the \*.

**Non-goals**

- Changing official scores. Fixing a typed-sheet mistake is still a re-import. On 10/25 two shooters were typed without the credit and were fixed by hand before import.
- Partial drops, where a station is dropped for some squads only. The admin override marks the station, and nothing more.
- Special shoots (`events.kind = 'special'`) are already out of every score frame and are not touched. Detection skips them.
- Recomputing anything for a Sunday with no station sheet. Without hits there is nothing to detect. An admin can still force a drop by rule, which then excludes the Sunday's rounds from score stats; see D3.

**Anti-goals** (a failure even if it "works")

- A thrown-out Sunday disappearing from the results, standings, race, attendance, streaks or clays-broken totals.
- Any "100%", "everyone cleaned it", "easiest station" or station-clean trophy that comes from a thrown-out station.
- Numbers that quietly leave rows out without the explainer saying so.
- A Sunday that looks like partial results. The client today reads `field_median === null` as partial; see D7.

---

## 2. Owner rules that bind this spec

| Rule (memory) | Where |
|---|---|
| Thrown-out station = perfect for every shooter, even if shot (2026-10-25) | §1, D1 |
| Official score counts for that week and overall, shown with \*; kept out of stats (2026-10-25) | §4 classes |
| Every chart has an ELI5 explainer; disclose exclusions where they happen | §6 |
| Spreadsheet scores are authoritative; station detail kept only if it sums | Unchanged. Detection reads the sheet as imported |
| Named-shooter insights positive or neutral; copy never he/she/his/her, no "class" | §6 copy; existing lints |
| Real names never in tracked files | Tests use invented names only |
| Images amd64+arm64, no named volumes, expand-only migrations | §8 rollout |

---

## 3. Data model and detection

### 3.1 Schema (migration `0010_thrown_out_stations`, expand-only)

- `station_layouts.dropped BOOLEAN NOT NULL DEFAULT false`
- `station_layouts.dropped_source TEXT NULL` with CHECK `IN ('auto','override')`
- `events.stats_excluded BOOLEAN NOT NULL DEFAULT false`. True when any station that day is dropped, or a Sunday-level override says so (D3).

Server defaults let the previous release keep running during the rollout. `event_metrics` and `round_metrics` keep their current nullability; see D6.

### 3.2 Detection (D1)

This runs in `domain/rebuild.py:rebuild_live` on regular Sundays only. Compute it from the staged station hits and the layouts **before** `_write_events`, the same way `specials` is passed in, so that `_write_events` can set `stats_excluded` and the `station_layouts` insert can set `dropped`.

A station `(event_date, station_label)` is auto-dropped when:

- the Sunday has at least **`MIN_DROP_ENTRIES = 8`** station-sheet entries for that station (my call; real turnouts are 13 to 40), and
- **every** entry, linked or not, has `hits == target_count`.

Checked against production on 2026-10-25, across 50 station Sundays and 351 station-days, the rule fires exactly twice: **2026-10-25 Station 11** (20/20) and **2026-01-11 Station 10** (24/24). No station has ever been one entry short of "all perfect", so the signal is clean.

Each detection raises a **DataIssue** at info level: "Station 11 on 2026-10-25 looks thrown out (every shooter perfect). It's marked \* and left out of stats. Override in Rules if that's wrong." The precedent is `incomplete_results` (rebuild.py:394). The import preview also adds a `station_dropped` finding. Its code goes into **both** `domain/imports.py:PREVIEW_STATION_CODES` and `frontend admin/components/FindingsList.tsx:STATION_CODES`.

### 3.3 Admin override (D3)

There is one new rule type, `station_drop`, with payload `{event_date, station_label | null, dropped: bool}`.

- `station_label` set: force that station on or off. `dropped_source = 'override'`.
- `station_label` null with `dropped: true`: mark the whole Sunday `stats_excluded` even when no station sheet exists. Use this for a day with a known drop but no sheet.
- Follow the `round_type_override` pattern: `ActiveRules`, applied in `_write_events` and the layouts insert, and `rule_target_missing` when nothing matches.
- `{station_label: null, dropped: false}` is rejected by payload validation. It has no meaning, because a Sunday is never excluded unless a station or a Sunday-level rule says so. (My call.)
- No reason field is stored. Copy never names a cause such as "equipment trouble". (My call.)
- `rules.rule_type` has no CHECK, so no migration is needed for the type. The frontend `admin-identity/rules.ts` (closed `RULE_TYPES`/`RULE_LABELS` union), `buildRulePayload` and `RuleCreateForm.tsx` need a new case, plus mocks.

---

## 4. The three classes

Every consumer in the appendix carries one of these classes:

| Class | Meaning | Examples |
|---|---|---|
| **Counts with \*** | Uses the official score or the round's existence; shown with \* where a score appears | That Sunday's results, rank, percentile, winners, podiums; race points; standings; Sundays/rounds/attendance; attendance streaks; clays broken/thrown and their milestones/trophies; the Sunday's own median and top score on its page, Latest card, share card, On this day and the weather Sunday list; first-timer counts |
| **Left out of score stats** | Statistics across rounds or Sundays | Every average/median across Sundays; best/PB/records/perfect rounds; distributions; first-round scores; trends and rolling lines; difficulty; expected/residual/adjusted; rating and skill updates; predictions; weather effects; score trophies and insights; Explore score/adjusted/residual/rating/difficulty |
| **Station left out of station stats** | Only the thrown-out station's hits are removed | All of `analytics/stations.py`; station trophies; `st.hardest-easiest`, `pf.station-best`; recap station feats and course stations; Explore hit % |

**Unaffected:** turnout, head counts, readiness, og facts, the page cache, and `classify_round_type`, because a dropped station keeps its target count.

---

## 5. How exclusion is carried (decisions)

**D4. One flag in the shared frames, filtered per consumer.** Do **not** reuse the special-shoot `WHERE kind='regular'` (it removes rows wholesale), and do **not** overload `held`/`results_complete`, which drive attendance streaks and placings.

- `frames._ROUNDS_SQL` and `_EVENTS_SQL` gain `e.stats_excluded`. `_STATION_HITS_SQL` gains `l.dropped`. Add them to `ROUND_COLUMNS`/`EVENT_COLUMNS`/`STATION_HIT_COLUMNS`, the `bools=` cast, and the test-world helpers (`appearances_from_rounds`, `calendar_from_events`) with default `False`.
- Add two helpers in `frames.py`: `stat_rounds(df)` (rows where not `stats_excluded`) and `live_station_hits(df)` (rows where not `dropped`). Score-stat consumers call `stat_rounds`. Station consumers call `live_station_hits` **before** `stations.add_sheet_totals`, so sheet totals leave out the free station.
- The duplicate SQL readers each gain the column or the filter: `stations._FRAME_SQL`, `achievements/context._STATION_SQL` (also add to `STATION_COLUMNS`, which `insights/trophies.py:_next_trophy` rebuilds from), `weather_effects._WEATHER_EVENTS_SQL`, `yir._EVENTS_SQL`, `predictions._scored_events` and `api/routes/claysmasher._STATIONS_SQL`. Folding them into `frames.py` is the builder's call. It is not required.

**D5. Skill and metrics.**

- In `skill._prepare` and the `s30` burn-in, treat a `stats_excluded` Sunday like a non-held one: no update, state carried forward, and `expected`/`residual`/`difficulty` NaN.
- `metrics.compute_round_metrics` keeps `field_median`, `event_rank`, `percentile` and `is_best_round`, because the day's own official numbers count, but sets `adjusted` to null for excluded rounds.
- Everything built on residual or adjusted then drops out on its own: form, bad-day rate, rust, learning curve, spotlight, weather sensitivity, biggest adjusted.

**D6. `event_metrics` stays whole.** The Sunday's own median and top score are official and shown with \*. No NOT NULL changes. Every **trend** consumer of event metrics filters on `stats_excluded`: `club_insights.event_trends`, `seasonality` mean median, yir hardest/easiest and months, weather `fit_club_model`/`band_summary`, insights `ev.how-it-played`, `toughest-since`, `week-jump`, `cl.rain-scores`, `weather-scoreboard`, and recap `scores_context`. The Sunday's own **difficulty** is a statistic, so it is not shown for that Sunday; it is already NaN from D5.

**D7. An explicit flag reaches the client.** Never infer "excluded" from nulls.

- Add `stats_excluded: bool` to `EventSummaryOut`, `EventDetailOut`, `EventResultOut`, `ShooterRoundOut`, `WinnerOut`, `PbOut` (always false, but kept for shape), `YirTopRoundOut`, `OnThisDayItemOut`, `RecordRoundOut` (always false), `WeatherEventOut`, `EventTrendOut` and `AttendanceOut`. Add `dropped: bool` to `StationLayoutOut`. Add `thrown_out: list[ThrownOutOut]` to `EventSummaryOut`/`EventDetailOut`/`RecapOut`, where `ThrownOutOut = {station_label: str | None, target_count: int | None, credited: bool}`. `credited` is true when every entry on that station has the full target count, which always holds for auto-detected drops. A Sunday-level override gives one item with `station_label = None`. (My call, from the builder check.)
- Use `json_schema_serialization_defaults_required=True` like `kind`/`target_total` do.
- `MePanel` must use the flag, not `field_median === null`. `isFinish` keeps using percentile, which is still set.

**D8. Ordered and prefix decisions (my calls).**

- **Skip, don't break.** In any score sequence (score streaks, `three-rising`, `tier-run`, `above-own-avg-streak`, `beat-field-streak`, records `_jumps`, trophy `_comeback`/`_above_average_3`), an excluded Sunday neither extends nor breaks the run. Its neighbours become adjacent. In insights, use `run_back` returning None.
- **Experience gates count every round shot.** The "≥ 5 earlier rounds" PB rule (all three copies: `personal_best.py`, `yir.pb_days`, `participation.personal_bests_value`; client `MIN_PB_EARLIER_ROUNDS`/`roundsBefore`), the tier ≥ 10 gate, the learning-curve career index `k`, rating-gain eligibility and the 5-round rating-record floor all count dropped-Sunday rounds, because the shooter really shot them. Only the *score* is left out of `prior_best`/`prior_sum`/`prior_mean`.
- **Mixed prefix structures split.** `achievements/context._shooter_days` and `insights/context.Day` keep `cum_rounds`/`cum_sum`/`targets`/`k`/`prior_rounds` over all rounds, and gain score-only `prior_best_s`/`prior_sum_s`/`prior_n_s` (names are the builder's call) that skip excluded rounds. `Day` and `Sunday` gain `stats_excluded`. `anchor_days`/`evergreen_days` gain a `scored_only` twin next to `held_only`.
- **Layoffs and rust use attendance.** A dropped Sunday the shooter attended still counts as attendance, so no fake layoff. Only its residual is excluded.
- **First round.** If a shooter's first Sunday is excluded, leave that shooter out of the first-round histogram and the `ev.new-faces` "strong start" part. Don't fall back to their second Sunday.
- **Average boards.** The minimum-rounds eligibility (`scaled_min_rounds`, `custom_min_rounds`) and the shown `n_rounds` on *average/best* boards count only rounds in the average. Count boards (wins, podiums, Sundays, rounds, points) count everything.
- **Profile stats.** `ShooterStatsOut`/`SplitOut` keep `n_rounds`/`n_events` official, and add `n_excluded: int` so the UI can say "2 rounds marked \* not in the average". YIR totals do the same.
- **`avg_percentile`** is a placing, so it counts. **Odometer hit rate** (broken ÷ thrown) is a statistic, so it leaves those Sundays out. Clays broken and thrown still count. Reword the copy that defines average as "clays broken ÷ rounds" (yir `glance`/`shooterYear`, shooters `odometer`, club `stat-clays`).
- **vs previous Sunday.** On an excluded Sunday the score deltas are hidden. The comparison for the next Sunday skips back to the last non-excluded Sunday.
- **Stations seen only as thrown out.** Leave them off the station lists, and `/api/stations/{label}` 404s as for an unknown label.
- **Explore.** Score metrics (score, adjusted, residual, rating, difficulty) always leave excluded Sundays out, **server-side in the engine**, so stored insight charts and `proof.py` agree. Hit % leaves out dropped stations. Rounds, shooters, wins and attendance count everything. No new Filters field.
- **Insights on the excluded Sunday.** Anchored score kinds (`pf.pb`, `tied-best`, `first-tier`, `ev.record-watch`, `ev.top-score`, drought kinds, `ev.spotlight`, …) say nothing about that Sunday. Count kinds (`ev.close-finish`, crowd, firsts, wins, podiums, `pf.targets-milestone`) still fire. `anchors.py` and `proof.py` apply the same exclusions.
- **Score trophies earned on an excluded Sunday are not awarded.** Recompute is retroactive. Weather/condition trophies that don't use score still award. `_mudder` (≥40 in rain) uses score, so it does not.
- **ClaySmasher export.** Export as recorded, with the Notes column set from the same copy function as the banner ("Station 11 thrown out; everyone credited 7/7").

---

## 6. What people see

**Marker.** The marker is a plain **\*** after the score. It has a `title` and an `sr-only` sentence ("Station 11 was thrown out; everyone was credited 7/7"). Follow the `PbTable "(early)"` pattern. Note that ★ already means a special shoot in the shooter calendar. Keep \* visually distinct, as a plain asterisk in the muted text colour and never a star glyph.

**Sunday page** (`EventDetailPage`):

- A `role="note"` banner in the partial-results style: "**Station 11 was thrown out.** Everyone was credited 7/7. Today's results and standings count, marked \*. These scores and Station 11 are left out of averages, PBs and station stats."
- **Copy variants (my call).** All copy (banner, \* tooltip/sr-only, recap line, ClaySmasher note) is built by one function per side, from `thrown_out`:
  - credited station: "Station 11 was thrown out; everyone was credited 7/7"
  - overridden station whose hits are not all full: "Station 11 was thrown out"
  - Sunday-level: "A station was thrown out this Sunday"
  - several stations: list them, "Stations 4 and 11 were thrown out"
- Results table scores get \*.
- In the station heatmap, the thrown-out column is greyed, its header reads "11 \*", and its cells show "credited".
- The difficulty stat and vs-previous card are hidden for that Sunday.
- Median and top score show with \*.

**Places that show \*:**

- events: `ResultsTable`, `EventList` summary line, `SeasonCalendar` tooltip
- home: `LatestEventCard`, `MePanel` last result
- the recap card
- share cards: `EventShareCard`
- profile: trend chart, finishes chart, Sunday calendar tooltip, tough-days
- YIR: On this day
- the weather Sunday list
- the Explore per-Sunday table where a count metric is shown

**Charts that plot rounds.** These are the profile trend chart, finishes chart and calendar, and the club score trend. They still plot the dropped-Sunday point, drawn hollow with \* in the tooltip. It contributes to no line, rolling average or PB pin. Client-side stats skip it: `pbRoundIds`, `trendLineByDate`, `distributionModel`, the `ClubPulse` high score, and PbTable's "earlier rounds" count, which per D8 still counts the round.

**CSV.** Chart CSVs add a `thrown_out` column (`yes`/blank) wherever round or Sunday rows appear, so "CSV exports all rows" still holds.

**Explainer disclosure** (§1 goal 5).

- Add shared lines in the existing constant style (`stations/explainers.ts` `SHEETS_ONLY`, leaderboards `FILTERS_APPLY`):
  - **Rounds:** "Sundays with a station thrown out (marked \*) are left out." Use it on every explainer classed *left out of score stats*.
  - **Station:** "A station thrown out on the day is left out." Use it on every station explainer.
  - **Counts:** "Sundays with a station thrown out count here, marked \*." Use it where a count or official score is shown and the reader might wonder, such as results, standings, race and clays broken.
- Run-time-built explainers (`boardExplainer` per metric, `explorerExplainer` per metric, `raceExplainer`) pick the line per metric. Give `raceExplainer` the metric.
- Add a glossary term `thrown-out-station`, modelled on `special-shoot` (`glossary/terms.ts`). The explainer lint then forces `terms` on every explainer that mentions it.
- Word caps: events and home are at about 95 words, and events `difficulty` is already at the cap. Tighten that copy to fit. Don't raise the cap.
- Pinned-string tests (records count, leaderboards strings, shooters/summary terms) are updated deliberately in the task that changes them.
- **Insight `how` bullets** are backend copy. `lints.py` bans "drop"/"dropped"/"event", so use "a station thrown out". Score kinds gain the rounds line in their `how`.

**Recap email** (admin recap → newsletter complement). On an excluded Sunday, add one line at the top, from the copy function: "Station 11 was thrown out this week. Everyone was credited 7/7, so this week's scores aren't used in averages, PBs or station stats." Score kinds drop out on their own (D8). Milestones, including clays broken with credited targets, still count. `RecapOut` gains `thrown_out: list[str]`.

---

## 7. Testing

- **TDD for every task.** Implementers show the failing test, then the passing one. Reviewers re-run new tests on the base to confirm they fail there (owner rule).
- **Backend.**
  - Unit tests for detection, including the threshold, an unlinked entry, a special Sunday, and the override on, off and Sunday-level.
  - A synthetic world in `tests/` with one thrown-out Sunday, asserting each class on representative consumers: one count, one stat, one station, one ordered sequence and one prefix gate.
  - Goldens (`backend/tests/golden/*`) change only where the fixture world gains a dropped station. Regenerate them deliberately in a single task and review the diff.
- **Insights.** `proof.py` tests must pass with the exclusions.
- **Frontend.**
  - Vitest/MSW. Every typed mock literal gains the new required fields.
  - Explainer lints and word caps stay green.
  - Coverage stays at or above 90%. `ratchets/` is never edited by task PRs.
- **E2E.** In `auth.setup`, after seeding, create a `station_drop` rule on a fixture Sunday. Then assert the banner, the \* and the excluded explainer line. Read expected values from the API, as existing specs do.

---

## 8. Rollout

1. Merge to `main`. CI builds multi-arch images and the deployer mirrors and updates the stack. Migration `0010` is expand-only.
2. The rebuild job runs on deploy or by admin recompute. It auto-detects **2026-10-25 Station 11** and **2026-01-11 Station 10**.
3. Verify in prod:
   - both Sundays show the banner and \*
   - Station 11 on 10/25 and Station 10 on 1/11 are gone from station stats
   - averages and PBs exclude both Sundays
   - standings and the race are unchanged
   - two info DataIssues appear
4. If 1/11 was not actually a thrown-out station, add a `station_drop` rule with `dropped: false`.

---

## 9. Left to the builder

- Helper names, and whether to fold the duplicate station SQL into `frames.py`.
- Exact `MIN_DROP_ENTRIES`, as long as it is at least 8 and documented in one place.
- Task split and order, keeping data model → detection → frames and skill → consumers by area → API → frontend → explainers → e2e.
- Small copy edits to fit word caps, within the rules in §6.
