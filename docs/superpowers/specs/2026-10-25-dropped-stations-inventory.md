# Thrown-out stations: consumer inventory (appendix)

Built 2026-10-25 by six read-only reviewers against `main` @ `79ee0d8`. Classes: CWS = counts with \*, XR = left out of score stats, XS = station left out of station stats, UN = unaffected. Where this table and the design spec disagree, the spec's decisions (§5 D4–D8) win.

## model

Lane: data model and pipeline plumbing, checked against the public repo at HEAD 79ee0d8 (backend/src/sunday_clays/...).

(a) Schema now. events (models/live.py:30-54) has event_date PK, round_type, round_type_source, head_count, n_rounds, n_shooters, has_scores, has_stations, results_complete, plus three columns added by migration 0008: kind TEXT NOT NULL default 'regular' (CHECK ck_events_kind IN ('regular','special')), label TEXT NULL and target_total SMALLINT NOT NULL default 50. rounds.score is the official score. station_layouts has PK (event_date, station_label) plus station_no (sort int), target_count and source_import_id. station_hits has event_date, station_no, station_label, sheet_id, entry_row, name_key, shooter_id?, round_id?, hits. There is no dropped or stats flag anywhere.

How special events are handled. One predicate, a SQL `WHERE e.kind = 'regular'`, written out by hand in every raw-SQL reader:
- frames._ROUNDS_SQL :146, _EVENTS_SQL :158, _STATION_HITS_SQL :178
- stations._FRAME_SQL :85
- achievements/context._STATION_SQL :76
- insights/store.py :218
- weather_effects :69
- predictions._scored_events :167
- api/routes/claysmasher.py :48/:60/:68
- yir.py :62, which filters in pandas on events['kind']

Special Sundays reach analytics only through the appearance frames: load_calendar :313, load_appearances :331 and load_special_rounds :339, plus load_special_station_hits :368, used only by the Sunday page. Constants are EVENT_KIND_SPECIAL and REGULAR_TARGETS=50 (frames.py:20-22). Consumers that need specials use kind as a frame column (streaks._special_dates :19, summary :100, achievements/context._attendance_days :145, insights/club.special_turnout :64, insights/attendance :173).

Main point for the designer: kind='special' REMOVES the whole Sunday from every score frame. That means no rank, no wins, no race points and no standings; the day survives only as an appearance. A dropped-station Sunday is CWS: placings, wins, points, rank and counts must still come from load_rounds. So the special mechanism is the precedent for how a flag travels (events column → frame column → filter) but NOT a predicate to reuse. Do not set kind='special'. Do not overload results_complete/held either. held drives far more than score stats: streaks.held_event_dates (streaks.py:13), the attendance trophies, insights held_dates/picks, club_insights, meta n_held_events and percentile. Making a dropped day non-held would stop it counting toward Sunday streaks and held-Sunday totals, which are CWS.

Closest existing XR switch is `held`. When it is False, metrics.compute_round_metrics (metrics.py:74,88-89,84) nulls field_median, adjusted and percentile but keeps event_rank and is_best_round. skill._run (skill.py:197-226) skips the update, carries state forward with drift, and leaves expected/residual/difficulty NaN. A new event-level flag can be combined with held at exactly those two spots.

(b) Detection and hooks.
- Latest migration is 0009 (0009_response_cache.py, down_revision 0008), so the next one is 0010. It should be expand-only, in the style of 0008: add events.stats_excluded BOOL NOT NULL default false and station_layouts.dropped BOOL NOT NULL default false. Server defaults let the previous release keep running.
- Detection belongs in domain/rebuild.rebuild_live (rebuild.py:96-144). Order now: _station_layouts :120, then _write_events :122, then _write_rounds :123, then _write_station_data :124, which reads ImportStationHit and links entries to rounds by score via station_link.link_station_entries :503.
- Because events are written BEFORE station hits are read, do one of two things. Either compute the dropped set from staged ImportStationHit plus layouts before _write_events and pass it in (as `specials` is passed), or UPDATE events/station_layouts after _write_station_data. _write_events builds each row dict at rebuild.py:380-392, which is where stats_excluded would go. The station_layouts insert is at rebuild.py:451-463, which is where dropped would go.
- Rule: every entry that day has hits == target_count at that station. Guard with a minimum number of entries, and probably skip kind='special' days.
- Precedent for raising an admin-visible DataIssue: the incomplete_results issue at rebuild.py:394-403.
- The import preview could add a finding to domain/imports.PREVIEW_STATION_CODES (imports.py:64).
- The ingest validator rejects hits above target_count (ingest/stations.py:248-251) and warns when a layout total is not 50 (validate.py:72-81). It never knows about drops, so detection relies on the sheet recording the credited full count.

Rules system (domain/rules.py). RuleType enum :58-66 has merge_shooter, rename_shooter, score_override, hide_round, round_type_override, set_status, station_reset and alias_name. Payload models live in PAYLOAD_MODELS :145. ActiveRules :157 and load_active_rules :263 carry them.
- There is no CHECK constraint on rules.rule_type (0001_initial.py:164, models/identity.py:41). A new rule type therefore needs no migration: add an enum value, a payload model, and handling in load_active_rules.
- The event-level override precedent is round_type_override. It is keyed by event_date in ActiveRules.round_types, applied in _write_events :367-368 with round_type_source='override', and raises rule_target_missing when no event matches (:405-418).
- station_reset is read raw by analytics/stations.py:90/126 (SQL on rules), not through ActiveRules.
- A drop rule would follow round_type_override (event_date plus station label, force on/off) and set something like stats_excluded_source.
- The admin API is api/routes/admin_rules.py:24-58, which validates against the RuleType enum. A new value appears automatically.
- Note that ScoreOverridePayload caps Score at 50 (rules.py:32).

How frames carry event flags. Every flag is an explicit SQL column, plus a tuple in ROUND_COLUMNS :24 / EVENT_COLUMNS :56 / CALENDAR_COLUMNS :108 / STATION_HIT_COLUMNS :83, plus a bools= cast in _frame. Rounds already carry `held` as e.results_complete AS held (:140). The synthetic test helpers appearances_from_rounds :373 and calendar_from_events :402 would need a default for any new flag.

The duplicated station SQL that must also gain l.dropped (or filter on it) is stations._FRAME_SQL :77-87, achievements/context._STATION_SQL :69-79, claysmasher _STATIONS_SQL :54-62 and insights/store :216-218 (readiness count only).

All loaders are memoised on data_version (cache.py:153). rebuild bumps it (rebuild.py:129) and so does run_pipeline (pipeline.py:65), so no cache work is needed; the response_cache from 0009 is also keyed by data_version.

The pipeline is rebuild_handler (rebuild_live, then run_pipeline). Steps run in this order: s10 metrics, s20 weather, s30 skill, s50 achievements, s60 insights. s50 and s60 call the inspect.unwrap'd loaders (s60_insights.py:27-41, achievements/context.py:279-290), so they pick up new frame columns for free.

(c) Special-event rounds are already kept out of averages, PBs and skill. The single predicate is `e.kind = 'regular'` in the frame SQL. Since s10, s30, predictions, achievements and insights all start from frames.load_rounds, special rounds never get round_metrics rows, rating_history or PB status. The exception is load_special_rounds, which is display only. This works because the rounds are left out entirely; it does not mask them as excluded within the frame. For dropped Sundays the analogue has to be a per-round or per-event boolean that stays IN the frames. Two ways to apply it:
- Centrally in s10/s30: null field_median, adjusted and residual, and skip the skill update.
- Per consumer, for raw-score stats: avg, best and PB use r.score directly, so a metric being NaN does not exclude them.

Other notes:
- rebuild._write_profiles counts n_rounds without special dates (rebuild.py:585). For a dropped Sunday those rounds should still count (CWS).
- compute_event_metrics (metrics.py:97-115) writes n, median, mean, stdev and top_score for every scored day. Keep these for the day itself (CWS); trend and club consumers must filter on the flag.

| consumer | uses | cls | status | computes | notes |
|---|---|---|---|---|---|
| backend/src/sunday_clays/models/live.py:Event (30) | other | MIXED | corrected | events table: kind/label/target_total present (Plan 17, mig 0008); no stats_excluded | Stale list said kind/label/target_total only on prod DB; they ARE in the public model (live.py:49-54). Add stats_excluded (+source?) here. |
| backend/src/sunday_clays/models/live.py:StationLayout (97) | station_hits | XS | confirmed | PK(event_date, station_label), station_no, target_count, source_import_id | Natural home for a `dropped` bool (station-level). |
| backend/migrations/versions/0009_response_cache.py | other | UN | new | latest migration (down_revision 0008) | Next migration = 0010. 0008_special_events.py is the expand-only precedent (server_default so the previous release keeps working). |
| backend/src/sunday_clays/domain/rebuild.py:rebuild_live (96) | both | MIXED | confirmed | clear + rebuild live tables; order layouts(120) -> _write_events(122) -> _write_rounds(123) -> _write_station_data(124) -> profiles | Best detection point. Events are written before hits are read: either precompute from staged ImportStationHit + layouts and pass in like `specials`, or UPDATE after _write_station_data. |
| backend/src/sunday_clays/domain/rebuild.py:_write_events (344) | dates_counts | CWS | corrected | has_scores, has_stations, results_complete (>=50% head count), round_type (override > special > stations), kind/label/target_total (380-392) | Now also writes kind/label/target_total. Round_type override handling (367-368, 405-418 rule_target_missing) is the event-level override precedent. Do not overload results_complete. |
| backend/src/sunday_clays/domain/rebuild.py:_write_station_data (442) | station_hits | XS | confirmed | inserts station_layouts (451-463) and station_hits linked to rounds via link_station_entries (503); emits station DataIssues | Hits are in hand here (totals per entry, 478-482). This is where to compute and persist dropped and raise an informational DataIssue. |
| backend/src/sunday_clays/domain/rebuild.py:_write_profiles (553) | dates_counts | CWS | new | shooter_profiles n_rounds (excludes special dates, 585), n_events, first/last_event | Dropped-Sunday rounds must still count here (unlike special). |
| backend/src/sunday_clays/domain/rebuild.py:_with_special_rows/_live_rounds/_one_round_per_special_shooter (180/211/280) | scores | UN | new | special-event row ownership and identity resolution | Special-only plumbing; not affected. |
| backend/src/sunday_clays/domain/station_link.py:link_station_entries (55) | station_hits | UN | confirmed | links station entries to rounds by exact score, then by ordinal; station_score_mismatch etc. | Linking by score still works if the sheet records the credited full count, since total == official score. Detection must use every entry (linked or not) for the 'every shooter' test. |
| backend/src/sunday_clays/domain/rules.py:RuleType/PAYLOAD_MODELS/load_active_rules (58/145/263) | other | UN | new | overlay rules; round_type_override keyed by event_date | No DB CHECK on rule_type, so a new rule type (e.g. station_dropped {event_date, station, dropped: bool}) needs no migration. Wire it into ActiveRules like round_types. The admin API (api/routes/admin_rules.py:24-58) validates against the enum automatically. |
| backend/src/sunday_clays/domain/imports.py:PREVIEW_STATION_CODES (64) / _preview_stations (553) | station_hits | UN | new | import-preview station findings | Optional hook: a preview finding like 'station 4 looks dropped' at import time. |
| backend/src/sunday_clays/ingest/stations.py:_hits_row (228) + ingest/validate.py:_sheet_findings (67) | station_hits | UN | new | hits_out_of_range (0..target_count), layout_total_not_50 warning | Ingest has no drop concept. Detection depends on the sheet recording the full count; hits > target_count are rejected. |
| backend/src/sunday_clays/ingest/special.py:parse_special (58) | both | UN | new | special-event sheet: label, date, per-shooter station hits and recomputed total (special_total_mismatch) | Specials have stations too. Decide whether drop detection applies to kind='special' (probably skip). |
| backend/src/sunday_clays/analytics/frames.py:_ROUNDS_SQL/load_rounds (134/244) | scores | MIXED | corrected | all regular rounds + round_metrics + weather; held = results_complete | Now filters WHERE e.kind='regular' (146), so special rounds are absent. Dropped rounds must stay IN (for CWS); add a stats_excluded column to ROUND_COLUMNS (24) + bools. This is the central hook for all XR consumers. |
| backend/src/sunday_clays/analytics/frames.py:_EVENTS_SQL/load_events (149/300) | both | MIXED | corrected | regular events + event_metrics (n, median, mean, stdev, top_score, difficulty) + weather | Filters kind='regular' (158). Add stats_excluded to EVENT_COLUMNS (56) so trend consumers can filter. |
| backend/src/sunday_clays/analytics/frames.py:load_calendar (313) | dates_counts | CWS | new | every Sunday incl. special, + kind/label/target_total | Appearance/turnout consumers; CALENDAR_COLUMNS (108) derives from EVENT_COLUMNS, so a new flag flows in. |
| backend/src/sunday_clays/analytics/frames.py:load_appearances (331) | dates_counts | CWS | new | one row per shooter per Sunday shot, special included | Unaffected by drops (attendance). |
| backend/src/sunday_clays/analytics/frames.py:load_special_rounds / load_special_station_hits (339/368) | both | UN | new | special-only display frames | Display only, never stats. |
| backend/src/sunday_clays/analytics/frames.py:_STATION_HITS_SQL/load_station_hits (172/362) | station_hits | XS | corrected | regular station_hits joined to layouts (target_count) | Filters kind='regular' (178). Add l.dropped to STATION_HIT_COLUMNS (83), or filter it out; feeds s60 insights. |
| backend/src/sunday_clays/analytics/frames.py:appearances_from_rounds / calendar_from_events (373/402) | dates_counts | UN | new | synthetic appearance/calendar frames for callers and tests holding only rounds/events | Must default any new flag (False) or tests and callers break. |
| backend/src/sunday_clays/analytics/stations.py:_FRAME_SQL/load_station_frame (77) | station_hits | XS | confirmed | duplicate station-hit SQL with display_name | Has its own WHERE e.kind='regular' (85); needs the dropped filter too. Not a frames.py consumer. |
| backend/src/sunday_clays/analytics/achievements/context.py:_STATION_SQL (69) | station_hits | XS | confirmed | duplicate station-hit SQL for station trophies | Own kind filter (76); needs the dropped filter. |
| backend/src/sunday_clays/api/routes/claysmasher.py:_ROUNDS_SQL/_STATIONS_SQL/_LAYOUTS_SQL (41/54/64) | both | MIXED | corrected | per-shooter regular rounds + linked station hits export | Merged in public (stale list said unmerged branch). Filters kind='regular'. Should export the dropped station flag / star. |
| backend/src/sunday_clays/analytics/insights/store.py (216) | station_hits | UN | confirmed | count of station-sheet Sundays (readiness) | Readiness only; kind='regular' filter. |
| backend/src/sunday_clays/analytics/cache.py:cached_by_data_version (153) | other | UN | confirmed | per-process memo keyed by data_version | No change: rebuild and pipeline bump data_version. |
| backend/src/sunday_clays/analytics/pipeline.py:run_pipeline (59) | other | UN | confirmed | discovers steps s10..s60 in order, bumps data_version | No dedicated detection step needed if detection is done in rebuild. |
| backend/src/sunday_clays/analytics/metrics.py:compute_round_metrics (58) | scores | MIXED | confirmed | field_median/adjusted (.where(held)), event_rank, is_best_round, percentile (.where(held)) | rank/is_best CWS; field_median/adjusted XR (mask with held & ~stats_excluded at 88-89); percentile ambiguous (placement-based but averaged downstream). |
| backend/src/sunday_clays/analytics/metrics.py:compute_event_metrics (97) | scores | MIXED | confirmed | per-day n, median, mean, stdev, top_score | The day's own numbers are CWS (shown with *); club trends and medians that read event_metrics must filter (XR). |
| backend/src/sunday_clays/analytics/steps/s10_metrics.py:run (22) | scores | MIXED | confirmed | rewrites round_metrics + event_metrics from load_rounds | Gets the flag via load_rounds; follows compute_* above. |
| backend/src/sunday_clays/analytics/skill.py:_prepare/_run/run_skill_model/calibrate (130/168/263/282) | scores | XR | confirmed | Kalman skill/rating, difficulty, expected/residual; only held events update | _prepare sets held=group['held'] (144). Change it to held & ~stats_excluded so dropped days are skipped like non-held days (state carried, residual/difficulty NaN). Calibration burn-in counts held events (199). |
| backend/src/sunday_clays/analytics/steps/s30_skill.py:run (70) | scores | XR | confirmed | writes expected/residual/mu, difficulty, rating_history; burn-in check rounds['held'] (83) | Line 83 burn-in count should use the same combined predicate. |
| backend/src/sunday_clays/analytics/predictions.py:skill_snapshot (155) | scores | XR | confirmed | re-runs skill model on load_rounds | Follows skill._prepare. |
| backend/src/sunday_clays/analytics/predictions.py:next_predictions (185) / attendance_probs (76) / _scored_events (165) | both | MIXED | confirmed | expected scores (XR via snapshot), attendance prob over last 13 scored regular Sundays | attendance_probs UN (a dropped Sunday is a real attendance); expected/field_median XR via skill. |
| backend/src/sunday_clays/analytics/steps/s20_event_weather.py:run (24) | other | UN | new | event_weather for all events | Unaffected. |
| backend/src/sunday_clays/analytics/steps/s50_achievements.py:run (43) -> achievements/context.build_context (279) | both | MIXED | confirmed | reads unwrapped load_rounds/events/appearances/calendar + own station SQL | Gets the new frame columns for free; achievements/context._shooter_days (101) prior_best/cum split still needed (other lane). |
| backend/src/sunday_clays/analytics/steps/s60_insights.py:build_frames (27) | both | MIXED | confirmed | InsightFrames from unwrapped loaders incl. load_station_hits | Gets the flags for free once the frames carry them. |
| backend/src/sunday_clays/analytics/streaks.py:held_event_dates/streaks (13/26) | dates_counts | CWS | confirmed | attendance streaks over results_complete dates; special extends but is skipped | Evidence that held must NOT be overloaded: a non-held Sunday is skipped by streaks. |
| backend/src/sunday_clays/analytics/weather_effects.py:_WEATHER_EVENTS_SQL (64) | scores | XR | corrected | raw SQL over events + event_metrics for weather regression | Own SQL with kind='regular' (69), not via frames; must also filter stats_excluded. |
| backend/src/sunday_clays/analytics/yir.py:_EVENTS_SQL (23) / regular filter (62) | both | MIXED | new | own events SQL incl. kind; pandas regular filter | Separate SQL that needs stats_excluded selected (other lane for the logic). |
| backend/src/sunday_clays/api/routes/meta.py (19-27) | dates_counts | CWS | new | raw counts of events/rounds/held/station events | Counts include specials and dropped days; fine as is. |

Open questions:
- Should drop detection run on kind='special' Sundays (they have station grids), or only on regular Sundays?
- Persist both station_layouts.dropped and events.stats_excluded, or derive stats_excluded = any(dropped)? Should an admin rule be able to force the event flag without naming a station?
- Minimum-entries guard for auto-detect (e.g. at least 3 station entries that day) so one perfect squad's clean station isn't flagged as dropped?
- percentile (round_metrics) on a dropped Sunday: keep it (placement, CWS) or null it (it feeds avg-percentile stats, XR)?
- Apply XR centrally (s10 nulls field_median/adjusted, s30 skips the skill update) and also expose rounds.stats_excluded for raw-score consumers (avg/best/PB read r.score directly)? Both seem required.
- Should the station_hits for a dropped station still link and sum to the official score (the free credited targets), so station_link keeps exact-score matches? The design assumes the sheet records the full count.

## analytics

Lane: analytics core + achievements, public repo the repo @ 79ee0d8. Nothing for dropped stations exists yet (no `dropped`/`stats_excluded` anywhere in backend/src).

STRUCTURAL FACTS FOR THE DESIGNER
1. The special-event exclusion is NOT a per-consumer predicate. It is a SQL WHERE clause in the frame loaders. Score frames carry `WHERE e.kind = 'regular'`, so special Sundays never reach them. A separate pair of appearance frames does include specials. In backend/src/sunday_clays/analytics/frames.py:
   - _ROUNDS_SQL L134-148 (WHERE L146)
   - _EVENTS_SQL L149-160 (L158)
   - _STATION_HITS_SQL L172-180 (L178)
   - _CALENDAR_SQL L161-171 (all kinds, adds kind/label/target_total)
   - _APPEARANCES_SQL L190-199 (all kinds)
   - _SPECIAL_ROUNDS_SQL / _SPECIAL_STATION_HITS_SQL (display only)
   - constants EVENT_KIND_REGULAR/SPECIAL/REGULAR_TARGETS at L20-22
   - helpers appearances_from_rounds L373 and calendar_from_events L402 (test worlds)
   Extending the same WHERE to dropped Sundays would be WRONG. It would also remove their wins, podiums, points, rounds counts and clays totals, which must count with a star (CWS). Dropped Sundays need a row-level flag carried through the frames, e.g. `stats_excluded` on rounds/events and `dropped` on station hits. Score-stat consumers then filter on it. CWS consumers keep the rows.

2. Duplicate SQL in this lane that also hard-codes `kind = 'regular'`. Each must get the new columns or flags:
   - stations.py _FRAME_SQL L77-88 (WHERE L85)
   - achievements/context.py _STATION_SQL L69-79 (L76)
   - weather_effects.py _WEATHER_EVENTS_SQL L61-71 (L69)
   - yir.py _EVENTS_SQL L23-29: no WHERE. It selects e.kind and filters in Python via yir._regular L60-62.
   - predictions.py _scored_events L165-169
   The ideal is to make all of these read frames.py.

3. Easiest central hook for the event-level XR consumers is event_metrics. If s10 (steps/s10_metrics.py run L22-34, compute_event_metrics metrics.py L97) writes NULL median/mean/top_score/difficulty for an excluded Sunday, several consumers already drop it via dropna or NaN handling:
   - club_insights.event_trends and seasonality mean_median
   - yir hardest/easiest
   - weather fit_club_model
   - on_this_day top/median
   Same for round_metrics field_median/adjusted/residual (compute_round_metrics L58-94). Then _avg_adjusted, biggest_adjusted, form, bad_day_rate, rust, learning_curve and weather sensitivity drop out automatically. Keep event_rank, is_best_round and percentile so wins, points and podiums still count. The difficulty and residual come from s30 skill, which must skip the Sunday (skill._prepare L130; burn-in held_seen L182-199).
   Caveat: the raw `score` column is read directly by many XR consumers. These still need an explicit filter: _avg_score, _best_score, records highest/perfect/jumps, floor_ceiling, yir avg/top/perfect/months/pb_days, band_summary mean_score, round_score/comeback/above_average/mudder/personal_bests trophies, summary average/best/pbs, first_round_scores.

4. Mixed structures where XR and CWS share one computation and need splitting:
   - achievements/context.py _shooter_days L101-129. Its cum_rounds/cum_sum (clays trophies) are CWS. Its prior_best/prior_sum/prior_rounds/prev_day_best/day_best (score trophies) are XR.
   - yir.year_totals L198-211 and _shooter_totals L284-296: rounds and clays are CWS, avg_score is XR.
   - summary.compute_summary L82-135.
   - profile.shooter_insights L215-253.
   - records.compute_records L232-318.
   Prefix counters (n_prior / earlier_count, the ">= 5 earlier rounds" PB rule) need a decision: does a dropped-Sunday round count toward the 5? The PB rule exists in three copies that should agree: personal_best.py L10, yir.pb_days L272-281, participation.personal_bests_value L102-113. summary._pbs_set L68-79 uses the first.

5. Order-dependent XR consumers. Filtering their rows changes adjacency or attendance, so plain filtering is not enough:
   - records._jumps L165-198 uses Sunday positions over has_scores events. Decide whether the event before and the event after a dropped Sunday become adjacent or the jump is lost.
   - profile.rust_effect / _post_layoff_mask L138-169 detects layoffs from attended dates. A dropped Sunday the shooter attended must still count as attendance, or a fake layoff appears. Only the residual means exclude it.
   - learning_curve career index k L102-135.
   - cohorts.first_round_scores L102-117. A shooter whose first Sunday is the dropped one must be excluded. Do not fall back to their second Sunday.
   - records._highest_ratings 5-round count L201-229.

6. Window-size counts. leaderboards.scaled_min_rounds L136 and custom_min_rounds L148 count scored Sundays in the window for the average-board minimum. Decide whether a dropped Sunday counts as one. leaderboard_history.history_dates L35 frames every has_scores Sunday, so a dropped Sunday still gets a frame; that is fine.

7. Stations. stations.add_sheet_totals L98-103 is computed before any filtering. The separator L212 centres within the event, so a constant credited 7 cancels out either way, but the order of drop-then-total should be kept deliberate. achievements/stations.py reuses stations.per_event_station_pct. A dropped station at 100% would never be "hardest", but station_cleaner would award cleans on it. Exclude the dropped station's rows from ctx.station_hits at the context loader.

8. Stale-inventory corrections:
   - No weather_effects_*, yir_*, classes.py or predictions_* split files exist.
   - New analytics files since the stale inventory: personal_best.py, summary.py, club_milestones.py, recap_facts.py, recap_insights.py, recap_trophies.py. Recap files are in the insights/recap lane and were not deep-read here.
   - Achievements are recomputed in s50 from build_context (context.py L279-290) and persisted. Excluding rows there retroactively removes awards earned on a dropped Sunday.

| consumer | uses | cls | status | computes | notes |
|---|---|---|---|---|---|
| backend/src/sunday_clays/analytics/frames.py:_ROUNDS_SQL/load_rounds (134,244) | scores | MIXED | confirmed | central rounds frame (regular only) with metrics, held | Central hook. Special-event exclusion is `WHERE e.kind='regular'` L146. A dropped Sunday must NOT be added to this WHERE (wins/points must stay). Add a stats_excluded column instead. held = results_complete; do not overload it. |
| backend/src/sunday_clays/analytics/frames.py:_EVENTS_SQL/load_events (149,300) | scores | MIXED | confirmed | regular events + event_metrics + weather | WHERE kind='regular' L158. Add a stats_excluded column. The event_metrics NULL approach makes many event-level XR consumers self-excluding. |
| backend/src/sunday_clays/analytics/frames.py:_CALENDAR_SQL/load_calendar (161,313) | dates_counts | CWS | new | every Sunday incl. special with kind/label/target_total | Appearance-side frame (Plan 17). Turnout, streaks and seasonality read it. Carry the dropped flag here for * markers. |
| backend/src/sunday_clays/analytics/frames.py:_APPEARANCES_SQL/load_appearances (190,331) | dates_counts | CWS | new | shooter x Sunday shot, special included | Already the attendance layer separate from scores. Dropped Sundays stay in as-is. |
| backend/src/sunday_clays/analytics/frames.py:_STATION_HITS_SQL/load_station_hits (172,362) | station_hits | XS | confirmed | regular station hits + target_count | WHERE kind='regular' L178. Add station_layouts.dropped or filter dropped station rows here. Special grids go through _SPECIAL_STATION_HITS_SQL L181. |
| backend/src/sunday_clays/analytics/frames.py:appearances_from_rounds/calendar_from_events (373,402) | other | UN | new | test-world implied appearance/calendar frames | Needs default dropped/stats_excluded columns (False) if the flags are added to the frames. |
| backend/src/sunday_clays/analytics/leaderboards.py:_avg_score (287) | scores | XR | confirmed | mean score per shooter in window | Reads raw score, so it needs an explicit filter. n_rounds from the same agg drives min-rounds eligibility (L366). |
| backend/src/sunday_clays/analytics/leaderboards.py:_avg_adjusted (291) | scores | XR | confirmed | mean adjusted | Self-excludes if s10 writes NULL adjusted for the excluded Sunday (filters adjusted.notna()). |
| backend/src/sunday_clays/analytics/leaderboards.py:_best_score (295) | scores | XR | confirmed | max score | Raw score; needs a filter. |
| backend/src/sunday_clays/analytics/leaderboards.py:_wins/_podiums/_finishes (309-319) | scores | CWS | confirmed | count best rounds rank<=1/3 | Uses event_rank + is_best_round; keep those metrics on dropped Sundays. |
| backend/src/sunday_clays/analytics/leaderboards.py:_events/_rounds (299,305) + EVENTS appearances branch (441-445) | dates_counts | CWS | confirmed | Sundays / rounds counts | The EVENTS board already reads appearances (special included) unless a gauge filter is set. |
| backend/src/sunday_clays/analytics/leaderboards.py:_rating_gain (386) | scores | XR | confirmed | mu now - mu at window start; eligibility n_before>=10, n_inside>=min | mu comes from skill (XR at the source). The n_before/n_rounds round counts are ambiguous: decide whether excluded rounds count toward eligibility. |
| backend/src/sunday_clays/analytics/leaderboards.py:scaled_min_rounds/custom_min_rounds (136,148) | dates_counts | AMBIGUOUS | new | min rounds for avg boards from # scored Sundays in window | If dropped Sundays are excluded from averages, they should likely not count in E/n either; otherwise a 1-Sunday window demands an unreachable minimum. |
| backend/src/sunday_clays/analytics/leaderboards.py:active_shooter_ids (377) | dates_counts | CWS | new | >=5 rounds ever and >=1 in last 364d | Used by api/routes/shooters.py:330 and insights/trophies.py:107. Attendance-like. |
| backend/src/sunday_clays/analytics/leaderboards.py:_tie_keys/_shooters_as_of (334,352) | other | UN | new | D6 tie key from name_key | Unaffected. |
| backend/src/sunday_clays/analytics/points.py:event_points/season_points (17,30) | scores | CWS | confirmed | 10-8-6.. by best-round rank +1 participation | Needs is_best_round/event_rank kept on dropped Sundays. |
| backend/src/sunday_clays/analytics/leaderboard_history.py:leaderboard_history/history_dates (35,39) | both | MIXED | confirmed | per-scored-Sunday frames of leaderboard() | Follows each metric's class. history_dates uses has_scores, so a dropped Sunday gets a frame (keep it, starred). |
| backend/src/sunday_clays/analytics/streaks.py:streaks/held_event_dates/_special_dates (13-60) | dates_counts | CWS | confirmed | attendance streaks; special Sundays extend but never break | Treat the dropped Sunday as an ordinary regular held date. Do not reuse _special_dates (that would stop it breaking streaks). |
| backend/src/sunday_clays/analytics/records.py:compute_records highest_scores (290) | scores | XR | confirmed | top round scores | Raw score; filter past_rounds. |
| backend/src/sunday_clays/analytics/records.py:compute_records perfect_rounds (267,291) | scores | XR | confirmed | score==50 list | A 50 incl. a free 7 must not appear. |
| backend/src/sunday_clays/analytics/records.py:compute_records biggest_adjusted (268,292) | scores | XR | confirmed | top adjusted | Self-excludes if adjusted is NULL. |
| backend/src/sunday_clays/analytics/records.py:_jumps (165) | scores | XR | confirmed | score gain between consecutive scored Sundays attended | Position-based: `order` = has_scores event dates. Decide whether a dropped Sunday is removed from `order` (before/after become adjacent) or just from rounds (the jump across it is lost). |
| backend/src/sunday_clays/analytics/records.py:_highest_ratings (201) | scores | XR | confirmed | peak mu after 5th round | mu is XR at the source. The 'seen' 5-round count (L205-210) is ambiguous. |
| backend/src/sunday_clays/analytics/records.py:compute_records most_events/longest_streaks (285-295) | dates_counts | CWS | confirmed | Sundays attended, longest run | Reads appearances+calendar. |
| backend/src/sunday_clays/analytics/profile.py:floor_ceiling (77) | scores | XR | confirmed | P10/P90 last 20 scores | Raw score; needs a filter. |
| backend/src/sunday_clays/analytics/profile.py:bad_day_rate/form (86,92) | scores | XR | confirmed | residual share <=-6; mean residual last 5 | Self-excludes if residual is NULL. |
| backend/src/sunday_clays/analytics/profile.py:event_values/learning_curve (102,115) | scores | XR | confirmed | adjusted by career event index k vs club median | Self-excludes via adjusted NULL, but k then skips the dropped Sunday (it renumbers). Decide. |
| backend/src/sunday_clays/analytics/profile.py:rust_effect/_post_layoff_mask (138,156) | scores | MIXED | corrected | mean residual after 28-day layoff minus elsewhere | Layoff detection must use attendance INCLUDING the dropped Sunday. Only the residual means exclude it. Filtering rows before the call would create fake layoffs. |
| backend/src/sunday_clays/analytics/profile.py:peak (172) | scores | XR | confirmed | highest mu | Follows skill. |
| backend/src/sunday_clays/analytics/profile.py:shooter_insights wins/podiums/milestone (245-252) | dates_counts | CWS | confirmed | wins, podiums, Sundays milestone | milestone already reads appearances. n_rounds L238 is CWS. |
| backend/src/sunday_clays/analytics/profile.py:shooter_insights avg_percentile (235,247) | scores | AMBIGUOUS | confirmed | mean percentile of best rounds | Percentile is placing-based (CWS-ish) but shown as a skill stat. Owner decision. |
| backend/src/sunday_clays/analytics/cohorts.py:cohort_tables/newcomer_cohorts/cohort_returns (28-99) | dates_counts | CWS | confirmed | cohort retention by dates | Date-only. |
| backend/src/sunday_clays/analytics/cohorts.py:first_round_scores (102) | scores | XR | confirmed | first-Sunday best score per shooter | Compute 'first' over all rounds, THEN drop shooters whose first Sunday is excluded. Do not fall back to their 2nd Sunday. Callers: api/routes/club.py:264, insights/anchors.py:274. |
| backend/src/sunday_clays/analytics/club_insights.py:regulars/_core_counts (100,114) | dates_counts | CWS | confirmed | core/lapsed regulars |  |
| backend/src/sunday_clays/analytics/club_insights.py:guest_conversion (145) | dates_counts | CWS | confirmed | guest->member conversion |  |
| backend/src/sunday_clays/analytics/club_insights.py:parity (181) | scores | CWS | confirmed | distinct winners, top-3 share, favorite win rate (mu_before) | Rank-based. mu_before on a dropped Sunday = carried skill, fine. |
| backend/src/sunday_clays/analytics/club_insights.py:yearly_trends (223) | dates_counts | CWS | confirmed | Sundays held, head counts, unique shooters, ytd rounds | Already takes calendar+appearances. |
| backend/src/sunday_clays/analytics/club_insights.py:event_trends (271) | scores | XR | confirmed | per-event top/median/difficulty + rolling-8 | Already dropna on top_score/median, so it self-excludes if event_metrics are NULL. Rolling-8 is over rows, so the window just skips it. |
| backend/src/sunday_clays/analytics/club_insights.py:seasonality (298) | both | MIXED | confirmed | per month n_events, mean head count, mean median | Route passes the calendar (api/routes/club_insights.py:137). n_events/head_count CWS; mean_median XR (self-excludes via NULL median). |
| backend/src/sunday_clays/analytics/weather_effects.py:_WEATHER_EVENTS_SQL/load_weather_events (61,431) | scores | MIXED | new | duplicate events+metrics+weather SQL | Its own copy of the `WHERE e.kind='regular'` predicate (L69). Needs the flag or a switch to frames. |
| backend/src/sunday_clays/analytics/weather_effects.py:fit_club_model/club_regression (211,450) | scores | XR | confirmed | WLS of difficulty on weather | dropna difficulty, so it self-excludes if difficulty is NULL. Also feeds predictions.choose_difficulty. |
| backend/src/sunday_clays/analytics/weather_effects.py:band_summary/effects (263,466) | scores | XR | confirmed | per band n_events, n_rounds, mean_score, mean_difficulty | mean_score reads raw score via _score_rounds L442. Filter rounds AND events, or n_events counts the Sunday while its score is excluded. |
| backend/src/sunday_clays/analytics/weather_effects.py:shooter_sensitivity/z_scales (353,304) | scores | XR | confirmed | per-shooter residual-on-weather OLS | dropna residual, so it self-excludes. z_scales is weather-only (UN). |
| backend/src/sunday_clays/analytics/weather_effects.py:turnout (285) | dates_counts | UN | confirmed | head count by band |  |
| backend/src/sunday_clays/analytics/weather_effects.py:weather_event_rows (391) | both | MIXED | corrected | per-event row incl. n_rounds, median, mean, top, difficulty | n_rounds/head_count CWS. median/mean/top/difficulty become NULL under the event_metrics approach; the UI should show a star. |
| backend/src/sunday_clays/analytics/yir.py:_EVENTS_SQL/_regular (23,60) | dates_counts | MIXED | new | own events SQL incl. kind; Python regular filter | Third copy of the special predicate (Python `_regular`). Needs the flag. |
| backend/src/sunday_clays/analytics/yir.py:year_totals (198) | both | MIXED | confirmed | scored/held events, rounds, shooters, clays thrown/broken, avg_score | Counts and clays CWS (official score incl. the credited 7); avg_score L210 XR. |
| backend/src/sunday_clays/analytics/yir.py:club_year (229) | both | MIXED | confirmed | newcomers, perfect_rounds, top_rounds, months avg, busiest/hardest/easiest | perfect_rounds L257, top_rounds L237, months.avg_score L247 and hardest/easiest L264-265 (via NULL difficulty) are XR. newcomers, busiest and months.events are CWS. |
| backend/src/sunday_clays/analytics/yir.py:pb_days (272) | scores | XR | confirmed | PB days (>=5 earlier rounds) | One of three PB-rule copies. Decide whether excluded rounds count toward earlier_count. |
| backend/src/sunday_clays/analytics/yir.py:_shooter_totals/shooter_year (284,304) | both | MIXED | confirmed | shooter year totals, best, wins, podiums, pbs, rating, months | best/avg/pbs/months avg/rating XR; events/rounds/clays/wins/podiums/best_finish/attendance_rank CWS. |
| backend/src/sunday_clays/analytics/yir.py:on_this_day (362) | both | CWS | confirmed | event 1/2/3 years back: top, median, winners | Winners CWS (starred). top_score/median come from event_metrics, which would become NULL; prefer showing the official numbers with a star. |
| backend/src/sunday_clays/analytics/stations.py:_FRAME_SQL/load_station_frame (77,105) | station_hits | XS | confirmed | own duplicate station SQL | WHERE kind='regular' L85. add_sheet_totals L98 runs before filtering, so decide whether to drop the station before or after computing sheet_total. |
| backend/src/sunday_clays/analytics/stations.py:hit_stats/station_stats/_stat_row (191,236,247) | station_hits | XS | confirmed | hit%, CI, deff, clean_rate |  |
| backend/src/sunday_clays/analytics/stations.py:separator (212) | station_hits | XS | confirmed | corr of station share vs rest-of-sheet | Centred per event, so a credited constant in sheet_total cancels out. |
| backend/src/sunday_clays/analytics/stations.py:per_event_station_pct (255) | station_hits | XS | confirmed | per-event per-station hit% | Also used by achievements/stations.py. |
| backend/src/sunday_clays/analytics/stations.py:station_leaders/shooter_station_matrix/shooter_station_deltas (278,315,343) | station_hits | XS | confirmed | leaders, shooter x station matrix, shrunken deltas |  |
| backend/src/sunday_clays/analytics/stations.py:assign_eras/era_stats/station_wind (393,420,439) | station_hits | XS | confirmed | era splits, wind bands |  |
| backend/src/sunday_clays/analytics/stations.py:stations_overview/station_detail (493,524) | station_hits | XS | confirmed | page assemblies; n_events | station_order(assigned) lists stations. Decide whether a station seen only as dropped is listed. |
| backend/src/sunday_clays/analytics/predictions.py:attendance_probs/_scored_events (76,165) | dates_counts | UN | confirmed | P(attend) over last 13 scored Sundays | _scored_events has its own `WHERE kind='regular'` SQL. Attendance only. |
| backend/src/sunday_clays/analytics/predictions.py:skill_snapshot/next_predictions/choose_difficulty (155,185,102) | scores | XR | confirmed | skill rerun, expected scores, day difficulty | Follows skill.run_skill_model and weather club_regression exclusions. |
| backend/src/sunday_clays/analytics/achievements/context.py:_STATION_SQL/load_station_entries (69,274) | station_hits | XS | confirmed | duplicate station SQL for trophies | WHERE kind='regular' L76. Filter the dropped station here so every station trophy follows. |
| backend/src/sunday_clays/analytics/achievements/context.py:_shooter_days (101) | scores | MIXED | confirmed | per shooter-day n_rounds, day_best, cum_rounds, cum_sum, prior_*, prev_day_best | cum_rounds/cum_sum/n_events CWS (clays trophies); day_best/prior_best/prior_sum/prior_rounds/prev_day_best XR. Needs a split (e.g. scored-only prefix columns). best_round_id also feeds attendance_days. |
| backend/src/sunday_clays/analytics/achievements/context.py:_attendance_days/AchContext (132,155) | dates_counts | CWS | new | attendance view incl. specials | Existing regular-vs-appearance split. rounds/events/station_hits are regular only; appearances/calendar include specials. |
| backend/src/sunday_clays/analytics/achievements/participation.py:clays_broken_value/clays_thrown_value (52,57) | scores | CWS | confirmed | lifetime sum of scores / rounds*50 | Official score counts (incl. credited targets). |
| backend/src/sunday_clays/analytics/achievements/participation.py:events/years_active/big_year/iron_streak/new_year/anniversary/welcome_back/four_seasons/perfect_month/three_bird_shoot (62-298) | dates_counts | CWS | confirmed | attendance trophies |  |
| backend/src/sunday_clays/analytics/achievements/participation.py:doubleheader/joined_club/both_disciplines (116,204,218) | dates_counts | CWS | new | 2+ rounds a day, guest->member, both round types | Not in the stale list. |
| backend/src/sunday_clays/analytics/achievements/participation.py:personal_bests_value (102) | scores | XR | confirmed | cumulative PB count | Uses prior_best/prior_rounds from _shooter_days. Its own copy of the PB rule (PB_MIN_PRIOR_ROUNDS L25). |
| backend/src/sunday_clays/analytics/achievements/scores.py:round_score_value (26) | scores | XR | confirmed | best-round tiers 30..50 | cummax of day_best. |
| backend/src/sunday_clays/analytics/achievements/scores.py:_comeback (40) | scores | XR | confirmed | beat previous event best by 15 | prev_day_best must skip the excluded Sunday (decide whether the event after it compares to the one before). |
| backend/src/sunday_clays/analytics/achievements/scores.py:_above_average_3 (59) | scores | XR | confirmed | 3 events in a row above career avg | Run-of-3 adjacency: decide whether the excluded Sunday breaks or is skipped in the run. |
| backend/src/sunday_clays/analytics/achievements/conditions.py:_weather rain/cold/heat/wind, _all_weather, _sub_gauge (49,62,96) | dates_counts | CWS | confirmed | first round in given weather / sub-gauge | Participation-in-conditions. The score is only a tiebreak within a day. |
| backend/src/sunday_clays/analytics/achievements/conditions.py:_mudder (74) | scores | XR | confirmed | score>=40 in rain |  |
| backend/src/sunday_clays/analytics/achievements/competition.py:_first_win/_podium (26,33) | scores | CWS | confirmed | rank 1 / top 3 with >=5 shooters | Uses event_rank/is_best_round. |
| backend/src/sunday_clays/analytics/achievements/stations.py:station_cleaner_value (37) | station_hits | XS | confirmed | cumulative clean stations | A dropped station would be clean for everyone, so it must be excluded. |
| backend/src/sunday_clays/analytics/achievements/stations.py:_hardest_station_clean (53) | station_hits | XS | confirmed | clean on the day's lowest-hit% station | Uses stations.per_event_station_pct. |
| backend/src/sunday_clays/analytics/achievements/stations.py:_station_top_gun (83) | station_hits | XS | confirmed | sole top at a station, sheet >=5 entries | On a dropped station all shooters tie, so it awards nothing, but exclude it anyway. entry_row count is unaffected. |
| backend/src/sunday_clays/analytics/achievements/registry.py:evaluate_all/progress/progress_many (245,276,286) | other | MIXED | confirmed | award evaluation + next-trophy progress | Follows each definition. Awards are recomputed and persisted in s50 via build_context (context.py:279). |
| backend/src/sunday_clays/analytics/personal_best.py:is_new_pb (10) | scores | XR | new | shared PB rule (n_prior>=5, beats previous best) | Used by api/routes/events.py:347 and summary._pbs_set. Caller must pass previous_best/n_prior from non-excluded rounds. |
| backend/src/sunday_clays/analytics/summary.py:compute_summary/_pbs_set (82,68) | both | MIXED | new | shooter summary card: sundays, special_sundays, rounds, average, best, pbs_set, trophies, longest_streak | average/best/pbs_set XR; sundays/rounds/streak/trophies CWS. |
| backend/src/sunday_clays/analytics/club_milestones.py:compute_milestones (96) | dates_counts | CWS | new | club clays thrown (50*rounds), Sundays held, shooters, rounds crossings | Cumulative counts. Uses REGULAR_TARGETS*rounds. |
| backend/src/sunday_clays/analytics/metrics.py:compute_round_metrics/compute_event_metrics (58,97) | scores | MIXED | confirmed | field_median/adjusted/rank/percentile; event n/median/mean/stdev/top | Outside the lane list but the key hook. Null field_median/adjusted and the event median/mean/top for excluded Sundays; keep rank/is_best/percentile. Caller is steps/s10_metrics.py:22. |

Open questions:
- Do rounds shot on a dropped Sunday count toward 'N earlier rounds' thresholds? These are the PB rule's >=5 (personal_best.py:10, yir.pb_days:272, participation.personal_bests_value:102), above_average_3's >=10, comeback's >=5, rating-gain eligibility (leaderboards._rating_gain:386) and the 5-round rating-record floor (records._highest_ratings:205).
- In ordered stats, is the dropped Sunday skipped (its neighbours become adjacent) or does it break the sequence? This affects records._jumps:165, scores._comeback (prev_day_best) and _above_average_3 run, and learning_curve k-index (profile.py:102).
- Does a dropped Sunday count in the scored-Sunday count E that sets the average-board minimum (leaderboards.scaled_min_rounds:136, custom_min_rounds:148)?
- Is avg_percentile (profile.py:235) a placing stat (count it) or a score stat (exclude it)?
- On a dropped Sunday, should the per-day top_score/median show the official values with a * (on_this_day, weather_event_rows), or be null? Nulling event_metrics hides them in those day-level displays.
- Should a station that only ever appears as dropped still be listed on the stations pages (stations.station_order over the assigned frame)?
- Is the dropped flag carried as new columns on the shared frames (preferred), or does each duplicate SQL (stations._FRAME_SQL, achievements/context._STATION_SQL, weather_effects._WEATHER_EVENTS_SQL, yir._EVENTS_SQL, predictions._scored_events) get patched?

## insights

Lane: insights package + recap email, read from the public repo at HEAD 79ee0d8. Paths are relative to the repo root; A = backend/src/sunday_clays/analytics.

STRUCTURE THE DESIGNER NEEDS
1. How special Sundays are excluded today. It happens at the frame SQL. Every score frame filters `WHERE e.kind = 'regular'`: A/frames.py:146 (_ROUNDS_SQL), :158 (_EVENTS_SQL), :178 (_STATION_HITS_SQL). Only `appearances` (_APPEARANCES_SQL :190) and `calendar` (_CALENDAR_SQL :161) still see special Sundays. Inside insights, special Sundays come back only for appearance and turnout facts:
   - context.py: `special_days`, `appearances_through` :206, `specials_through` :210
   - attendance.py `_attended` :172
   - club.py `special_turnout` :64
   - milestones `pf.sunday-milestone` and `pf.back-strong` gap; journeys anniversary first date; sunday.py new-faces and second-visit first date; community `cl.year-wrap`; records `streak-chase` via streaks(appearances, calendar)
   - recap_facts attendance_streak and coming_up
   - admin_recap.py:120 gives special Sundays no "This week" lines at all; api/routes/insights.py:147 held_dates leaves special Sundays out.
   The dropped-station feature cannot copy this whole-row SQL filter. Those rounds must stay in `fr.rounds`, `Sunday.results` and `Day` for the counted-with-star (CWS) uses: rank, wins, points, counts and targets. They must leave only the score stats. So the frames need a flag column: a per-event `stats_excluded` on the rounds and events frames, and a per-row `dropped` on the station frame.

2. Central hook points:
   - A/steps/s60_insights.py:27 `build_frames`: the only builder of InsightFrames (also used by admin_recap.py:88).
   - A/insights/context.py:276 `_build_sundays`: Sunday.median, top, difficulty and results.
   - context.py:315 `_build_histories`: Day.
   - Day (:56) mixes prefix values. `targets` (:74) and `k` are CWS. `prior_best` (:72), `prior_sum` (:73, feeds `prior_mean` :88) and `prior_rounds` (:71, used as the eligibility gate for PB, tier, stretch and so on) feed score stats. Splitting off score-only prefixes such as prior_best_s, prior_sum_s and prior_n_s is needed. `targets` is computed as prior_sum + scores, so the split must keep targets on all rounds.
   - Shared helpers to extend: `anchor_days` :404 and `evergreen_days` :417 (they gate only on held, deceased and guest; no score filter); `held_only` :444 (a `scored_only` twin fits here); `split_by_rain` :448; `own_tier` :489; `run_back` :580 (a None from ok() skips a day without breaking the run, which is the natural place for an excluded day in score streaks).
   - Station frame: `fr.stations` (frames.STATION_HIT_COLUMNS) is read by insights/stations.py `entries_to` :46, anchors.station_rows :255, recap_facts `_stations` :213, and trophies.py:202 (`_next_trophy`, which rebuilds AchContext from `fr.stations[list(STATION_COLUMNS)]`). A new dropped column must also go into achievements.context.STATION_COLUMNS or that path loses it.

3. What fixes itself if the metrics step (s10) nulls round_metrics.adjusted, residual and expected for excluded rounds: every kind that reads Day.adjusted, residual or expected, or rounds.adjusted, already skips None. That covers pf.hot-form, beat-own-usual, gaining-on-field, best-day-vs-field, beat-field-streak, wet-strength, weather-steady, best-temp, tough-days, top-of-club, ev.spotlight, the rain-day better/steady names, the pf.digest-line 'usual' part, and the year-up field gate.
   If event_metrics median and difficulty are also nulled, these fix themselves too: ev.how-it-played, toughest-since, week-jump, cl.rain-scores, weather-scoreboard, the 'p' flag of home.sunday-recap, rain-day 'played', and recap_facts scores_context. Nulling the median or difficulty would also hide them from the event page, so the alternative is a Sunday.stats_excluded flag checked in each kind.

4. Kinds that read raw `Day.score` or `Sunday.top` / `results[].score` and need explicit filtering:
   - peaks: best-stretch, average-milestone, season-best
   - form: up-on-usual, year-up (raw part), years-up-run
   - milestones: pb, tied-best, first-tier, first-since 'score', back-strong 'score'
   - streaks: tier-run, three-rising (consecutive days[i-2:i+1]), above-own-avg-streak
   - tiers: all three kinds
   - records: drought-clock, drought-ended, perfect-rarity
   - sunday: record-watch, top-score, new-faces 'strong' (also the `first_rounds_before` pool)
   - community: cl.club-one-shooter
   - pf.year-wrapped 'best', home.sunday-recap 'pbs' (via is_pb), recap_facts `_improvement`
   - learning-curve goes through profile.learning_curve(fr.rounds); rating-high, most-improved and rank-climb go through the skill model and rating_gain. Those belong to other lanes.

5. Station false positives, the most visible risk. On a dropped station every entry has hits == target_count:
   - recap_facts `_station_feats` (A/recap_facts.py:569) would email "N shooters broke every target at Station X". It would also count the dropped station toward everyone's "broke every target at K of M stations".
   - `_course_stations` :328 would name the dropped station as the easiest at 100%.
   - In insights/stations.py, st.hardest-easiest and pf.station-best take hit % over all entries.

6. Anchored kinds use `anchor_days`, which only checks `day.held`. A dropped Sunday is held, so every score kind would fire on it unless filtered.

7. Wording constraints for the star explanation inside insight text: lints.py:15-18 bans "drop" and "dropped" in named clauses, and every `how` bullet and chart label is linted with force_named=True (registry.py:127, :141). The word "event" is banned everywhere (lints.py:26). Any explainer on an insight must use other wording, for example "a station thrown out" or "every shooter given full credit on one station". Also, `Kind.how` bullets are fixed per variant, so a per-Sunday disclosure needs a new variant or a param slot.

8. Chart proof (insights/proof.py:35) checks headline numbers against Explorer `run_query` or anchors.py sources. Whatever exclusion the kinds apply must be mirrored in anchors.py (trend_rows `pb`, `so_far`, `roll10`; highest_rows; first_round_rows) and in the Explorer, or the CI proof test fails.

9. The recap email (api/routes/admin_recap.py) has no field for a star or dropped station in RecapOut (:42). Its ELIGIBLE list (A/recap_insights.py:65) is mostly score-stat kinds: drought-ended and drought-clock, how-it-played, record-watch, toughest-since, the score streaks, average-milestone, best-stretch, the first-since score variant, more-high-rounds, three-rising, tier-run. On a dropped Sunday the email therefore thins out on its own once those kinds are fixed. MILESTONE_KINDS uses pf.targets-milestone (CWS, official score including the credited targets). The email's Milestones section also carries tiered trophy lines (recap_trophies.py) and club milestones (club_milestones: rounds, sundays_held, shooters, clays_thrown), all CWS or unaffected.

10. Unaffected infrastructure: engine.readiness_of :44 and store.py:215 (station Sundays count, regular only), rank.shares :46, select/picks, og/facts.py (count and round type only).

11. Registered kinds: 73 across 17 modules. New since the stale list are race.py (ev.close-finish moved there), conditions.py's four kinds, tiers.py's three kinds, the trophies module, and the recap modules outside the package: A/recap_facts.py, recap_insights.py, recap_trophies.py and api/routes/admin_recap.py.

| consumer | uses | cls | status | computes | notes |
|---|---|---|---|---|---|
| backend/src/sunday_clays/analytics/frames.py:_ROUNDS_SQL/_EVENTS_SQL/_STATION_HITS_SQL (134-179) | both | MIXED | confirmed | score/event/station frames, regular Sundays only (special excluded by WHERE e.kind='regular') | Precedent for special exclusion; dropped Sundays cannot be filtered here (CWS needs the rows) -> add stats_excluded/dropped columns. |
| backend/src/sunday_clays/analytics/steps/s60_insights.py:build_frames (27) | both | MIXED | new | builds InsightFrames from frames loaders + awards | Single entry point for insights and admin recap (admin_recap.py:88). Thread flags here. |
| backend/src/sunday_clays/analytics/insights/context.py:_build_histories/Day (315/56) | scores | MIXED | confirmed | per shooter-day best score, adjusted/residual/expected, rank, field_n, k, prior_rounds, prior_best, prior_sum, targets | targets,k,rank CWS; prior_best/prior_sum(prior_mean)/score XR; prior_rounds used as eligibility gates. Needs split prefixes; targets = prior_sum+scores must stay all-rounds. |
| backend/src/sunday_clays/analytics/insights/context.py:_build_sundays/Sunday (276/101) | scores | MIXED | confirmed | held Sunday n, head_count, median, top, difficulty, weather, results (score, rank) | results/rank/n CWS; median/difficulty/top-as-record XR. Add Sunday.stats_excluded. |
| backend/src/sunday_clays/analytics/insights/context.py:anchor_days/evergreen_days/held_only/split_by_rain/own_tier/run_back (404/417/444/448/489/580) | scores | MIXED | new | shared iteration and score helpers | anchor_days only checks held -> score kinds fire on dropped Sunday. run_back None=skip is natural exclusion hook. split_by_rain uses adjusted (auto if nulled). own_tier uses last 52 raw scores (XR). |
| backend/src/sunday_clays/analytics/insights/engine.py:readiness_of (44) | station_hits | UN | new | count of Sundays with station sheets (dormancy gate) | Whole-Sunday count; unaffected. |
| backend/src/sunday_clays/analytics/insights/store.py:readiness (215-232) | station_hits | UN | confirmed | SQL twin of readiness_of station Sundays (regular only) | Readiness only. |
| backend/src/sunday_clays/analytics/insights/rank.py:shares (46) | dates_counts | UN | new | rarity shares from fact counts, active shooters, shooter-Sundays | No score use. |
| backend/src/sunday_clays/analytics/insights/lints.py:NEGATIVE/EVENT_WORD (15-26) | other | UN | new | bans 'drop'/'dropped'/'event' in named clauses, how bullets and labels | Star/explainer wording in insights cannot say 'dropped' or 'event' (how bullets force_named, registry.py:127). |
| backend/src/sunday_clays/analytics/insights/proof.py:chart_table/proof_problems (35/188) | both | MIXED | confirmed | CI check that headline numbers match Explorer run_query or anchor rows | Explorer and anchors must apply the same exclusions as the kinds, or the proof test fails. |
| backend/src/sunday_clays/analytics/insights/anchors.py:trend_rows (56) | scores | XR | confirmed | score, adjusted, running pb max, so_far (prior_mean), roll10/roll20 | pb/so_far/roll must skip excluded days; score point itself may be shown with star. |
| backend/src/sunday_clays/analytics/insights/anchors.py:rating_rows (80) | scores | XR | new | rating mu series | Follows skill model. |
| backend/src/sunday_clays/analytics/insights/anchors.py:calendar_rows (92) | scores | CWS | new | score per day, month | Attendance calendar with the official score. |
| backend/src/sunday_clays/analytics/insights/anchors.py:finishes_rows (108) | scores | CWS | new | rank and field size per held day |  |
| backend/src/sunday_clays/analytics/insights/anchors.py:tough_days_rows (120) | scores | XR | new | difficulty vs adjusted | Auto if adjusted/difficulty nulled. |
| backend/src/sunday_clays/analytics/insights/anchors.py:learning_rows (132) | scores | XR | new | profile.learning_curve over fr.rounds | Depends on profile lane. |
| backend/src/sunday_clays/analytics/insights/anchors.py:results_rows (142) | scores | MIXED | new | day's score/rank (+ residual, adjusted) | score/rank CWS; residual/adjusted XR. |
| backend/src/sunday_clays/analytics/insights/anchors.py:highest_rows (166) | scores | XR | new | rounds >=48, perfect/high counts from fr.rounds | Records list. |
| backend/src/sunday_clays/analytics/insights/anchors.py:streak_rows (184) | dates_counts | CWS | new | attendance streaks (appearances+calendar) |  |
| backend/src/sunday_clays/analytics/insights/anchors.py:season_points_rows (195) | scores | CWS | new | event_points from rank |  |
| backend/src/sunday_clays/analytics/insights/anchors.py:newcomer_rows (219) | dates_counts | CWS | new | cohort_returns over fr.rounds | Uses fr.rounds while kind cl.newcomers uses appearances (existing inconsistency). |
| backend/src/sunday_clays/analytics/insights/anchors.py:board_rows/movers_rows (232/250) | scores | MIXED | new | leaderboard for link metric / rating_gain | Class per metric (leaderboards lane); movers XR. |
| backend/src/sunday_clays/analytics/insights/anchors.py:station_rows (255) | station_hits | XS | new | hit % per station over window | Must drop dropped-station rows. |
| backend/src/sunday_clays/analytics/insights/anchors.py:first_round_rows (272) | scores | XR | new | first-round score histogram |  |
| backend/src/sunday_clays/analytics/insights/attendance.py:_attendance_year pf.attendance-year (75) | dates_counts | CWS | confirmed | share of year's held Sundays shot |  |
| backend/src/sunday_clays/analytics/insights/attendance.py:_attendance_streak pf.attendance-streak (222) | dates_counts | CWS | confirmed | held run incl. specials |  |
| backend/src/sunday_clays/analytics/insights/attendance.py:_months pf.months-in-row (353) | dates_counts | CWS | confirmed | months in a row with a round |  |
| backend/src/sunday_clays/analytics/insights/attendance.py:_year_wrapped pf.year-wrapped (443) | scores | MIXED | corrected | sundays, targets (sum of scores), best score, best top-third finish; chart avg by month | Stale said CWS. sundays/targets/finish CWS; 'best' and the avg-by-month chart XR. |
| backend/src/sunday_clays/analytics/insights/club.py:_rain_turnout cl.rain-turnout (132) | dates_counts | UN | confirmed | head count wet vs dry |  |
| backend/src/sunday_clays/analytics/insights/club.py:_rain_scores cl.rain-scores (242) | scores | XR | confirmed | mean Sunday.difficulty wet vs dry | Auto if difficulty nulled. |
| backend/src/sunday_clays/analytics/insights/club.py:_weather_scoreboard cl.weather-scoreboard (352) | scores | XR | confirmed | difficulty by weather band |  |
| backend/src/sunday_clays/analytics/insights/club.py:_turnout_trend cl.turnout-trend (472) | dates_counts | UN | confirmed | head count by year / recent |  |
| backend/src/sunday_clays/analytics/insights/club.py:_year_pace cl.year-pace (630) | dates_counts | CWS | confirmed | rounds this year vs last |  |
| backend/src/sunday_clays/analytics/insights/community.py:_newcomers cl.newcomers (81) | dates_counts | CWS | confirmed | cohort sizes/returns from appearances |  |
| backend/src/sunday_clays/analytics/insights/community.py:_originals cl.originals (154) | dates_counts | CWS | confirmed | first Sunday's shooters still active |  |
| backend/src/sunday_clays/analytics/insights/community.py:_year_wrap cl.year-wrap (231) | dates_counts | CWS | confirmed | sundays, rounds, firsts, busiest turnout |  |
| backend/src/sunday_clays/analytics/insights/community.py:_club_one_shooter cl.club-one-shooter (341) | scores | XR | confirmed | 12-month average best round and its rank among shooters' means | Raw Sunday.results scores: explicit filter needed. |
| backend/src/sunday_clays/analytics/insights/conditions.py:_wet_strength pf.wet-strength (84) | scores | XR | confirmed | wet vs dry adjusted | Auto via adjusted None. |
| backend/src/sunday_clays/analytics/insights/conditions.py:_weather_steady pf.weather-steady (178) | scores | XR | confirmed | wet vs dry adjusted gap small | Auto via adjusted None. |
| backend/src/sunday_clays/analytics/insights/conditions.py:_best_temp pf.best-temp (322) | scores | XR | confirmed | adjusted by temp band | Auto via adjusted None. |
| backend/src/sunday_clays/analytics/insights/conditions.py:_tough_days pf.tough-days (449) | scores | XR | confirmed | adjusted on hard (difficulty) days vs rest | Auto via adjusted/difficulty None. |
| backend/src/sunday_clays/analytics/insights/form.py:_hot_form pf.hot-form (73) | scores | XR | confirmed | mean adjusted last N held days | Auto via adjusted None. |
| backend/src/sunday_clays/analytics/insights/form.py:_beat_own_usual pf.beat-own-usual (176) | scores | XR | confirmed | residual vs expected | Auto via residual None. |
| backend/src/sunday_clays/analytics/insights/form.py:_up_on_usual pf.up-on-usual (296) | scores | XR | confirmed | mean raw score recent vs before | Raw Day.score (includes non-held days): explicit filter needed. |
| backend/src/sunday_clays/analytics/insights/form.py:_year_up pf.year-up (415) | scores | XR | confirmed | raw year mean + adjusted gain | Raw part needs explicit filter. |
| backend/src/sunday_clays/analytics/insights/form.py:_years_up_run pf.years-up-run (532) | scores | XR | confirmed | 3-year rising raw means | Explicit filter. |
| backend/src/sunday_clays/analytics/insights/form.py:_gaining pf.gaining-on-field (650) | scores | XR | confirmed | adjusted gain windows | Auto via adjusted None. |
| backend/src/sunday_clays/analytics/insights/journeys.py:_charter pf.charter-shooter (51) | dates_counts | CWS | confirmed | shot the first Sunday and still active |  |
| backend/src/sunday_clays/analytics/insights/journeys.py:_shooter_anniversary pf.shooter-anniversary (141) | dates_counts | CWS | confirmed | years since first appearance | In recap ELIGIBLE. |
| backend/src/sunday_clays/analytics/insights/journeys.py:_targets_milestone pf.targets-milestone (249) | scores | CWS | confirmed | cumulative targets (sum of official scores) crossing 1000s | Owner rule: cumulative counts official incl. credited targets. Also the email's Clays Broken lines (recap_insights.milestone_sentences). |
| backend/src/sunday_clays/analytics/insights/milestones.py:_pb pf.pb (92) | scores | XR | confirmed | score > prior_best with >=5 prior rounds | Needs score-only prior_best; also used by home.sunday-recap and peaks.season_best. |
| backend/src/sunday_clays/analytics/insights/milestones.py:_tied_best pf.tied-best (229) | scores | XR | confirmed | score == prior_best above prior_mean |  |
| backend/src/sunday_clays/analytics/insights/milestones.py:_sunday_milestone pf.sunday-milestone (341) | dates_counts | CWS | confirmed | Sunday count levels incl. specials, to_go |  |
| backend/src/sunday_clays/analytics/insights/milestones.py:_wins pf.wins (515) | scores | CWS | confirmed | rank==1 career/year/count |  |
| backend/src/sunday_clays/analytics/insights/milestones.py:_back_strong pf.back-strong (676) | scores | MIXED | corrected | return after 180+ days; 'score' variant when score >= prior_mean | Stale said XR. Comeback itself CWS; 'score' variant XR. |
| backend/src/sunday_clays/analytics/insights/milestones.py:_first_tier pf.first-tier (797) | scores | XR | confirmed | prior_best -> score crosses 40/45/48 |  |
| backend/src/sunday_clays/analytics/insights/milestones.py:_first_since pf.first-since (930) | scores | MIXED | confirmed | first win/podium/45/40 in a year+ | win/podium CWS; score variants XR (and history lists of score>=level). |
| backend/src/sunday_clays/analytics/insights/milestones.py:_career_first pf.career-first (1071) | scores | CWS | confirmed | first podium/top third |  |
| backend/src/sunday_clays/analytics/insights/peaks.py:_best_stretch pf.best-stretch (84) | scores | XR | confirmed | 10-day raw mean vs earlier windows/career | Explicit filter. |
| backend/src/sunday_clays/analytics/insights/peaks.py:_average_milestone pf.average-milestone (192) | scores | XR | confirmed | rolling raw average crossing levels | Explicit filter. |
| backend/src/sunday_clays/analytics/insights/peaks.py:_rating_high pf.rating-high (321) | scores | XR | confirmed | rating mu at a high | Via skill model (other lane). |
| backend/src/sunday_clays/analytics/insights/peaks.py:_learning_curve pf.learning-curve (428) | scores | XR | confirmed | profile.learning_curve vs club median | Via profile.learning_curve(fr.rounds). |
| backend/src/sunday_clays/analytics/insights/peaks.py:_season_best pf.season-best (544) | scores | XR | confirmed | year's best raw score vs year mean, uses prior_best | Explicit filter. |
| backend/src/sunday_clays/analytics/insights/peaks.py:_best_day pf.best-day-vs-field (666) | scores | XR | confirmed | max adjusted | Auto via adjusted None. |
| backend/src/sunday_clays/analytics/insights/race.py:_close_finish ev.close-finish (29) | scores | CWS | corrected | ties at top / top-3 within one (top >= 45) | Path is now race.py (stale gave none). That week's results: CWS, but the 45 gate uses an official score that includes the credited targets. |
| backend/src/sunday_clays/analytics/insights/recap.py:_digest pf.digest-line (44) | scores | MIXED | confirmed | latest Sunday score, finish, residual 'over usual' | score/finish CWS; 'usual' (residual) XR, auto if nulled. |
| backend/src/sunday_clays/analytics/insights/recap.py:_sunday_recap home.sunday-recap (171) | scores | MIXED | confirmed | crowd, top score/tie, weather, played (difficulty), PB count, first-timers | n/top/tie/firsts/weather CWS/UN; 'p' and 'b' XR. |
| backend/src/sunday_clays/analytics/insights/records.py:_drought_clock rec.drought-clock (75) | scores | XR | confirmed | held Sundays since a 49+ top | In recap ELIGIBLE. |
| backend/src/sunday_clays/analytics/insights/records.py:_drought_ended ev.drought-ended (127) | scores | XR | confirmed | 49+ after a long wait | In recap ELIGIBLE. |
| backend/src/sunday_clays/analytics/insights/records.py:_perfect_rarity rec.perfect-rarity (221) | scores | XR | confirmed | perfect/high rounds of all rounds | Reads fr.rounds directly. |
| backend/src/sunday_clays/analytics/insights/records.py:_streak_chase rec.streak-chase (316) | scores | CWS | confirmed | attendance streak record chase; win streak chase (rank==1) |  |
| backend/src/sunday_clays/analytics/insights/season.py:_new_leader lb.new-leader (126) | scores | CWS | confirmed | points standings leader | event_points from rank. |
| backend/src/sunday_clays/analytics/insights/season.py:_title_race lb.title-race (193) | scores | CWS | confirmed | points lead vs Sundays left |  |
| backend/src/sunday_clays/analytics/insights/season.py:_biggest_climb lb.biggest-climb (270) | scores | CWS | confirmed | points rank climb |  |
| backend/src/sunday_clays/analytics/insights/season.py:_most_improved lb.most-improved (380) | scores | XR | confirmed | leaderboard RATING_GAIN YTD | Via leaderboards/skill. |
| backend/src/sunday_clays/analytics/insights/season.py:_rank_climb pf.rank-climb (502) | scores | XR | confirmed | RATING_GAIN rolling 12 | Via leaderboards/skill. |
| backend/src/sunday_clays/analytics/insights/season.py:_top_of_club pf.top-of-club (597) | scores | XR | confirmed | 12-month mean rounds.adjusted placement | Auto via adjusted NaN. |
| backend/src/sunday_clays/analytics/insights/stations.py:_hardest_easiest st.hardest-easiest (73) | station_hits | XS | confirmed | hit % by station across all entries | Filter in entries_to (46). |
| backend/src/sunday_clays/analytics/insights/stations.py:_station_best pf.station-best (163) | station_hits | XS | confirmed | own hit % vs field per station | Filter in entries_to (46). |
| backend/src/sunday_clays/analytics/insights/streaks.py:_beat_field pf.beat-field-streak (125) | scores | XR | confirmed | run of adjusted > 0 | above_field returns None when adjusted None, so the day is skipped (does not break the run). |
| backend/src/sunday_clays/analytics/insights/streaks.py:_own_avg pf.above-own-avg-streak (237) | scores | XR | confirmed | run of score > prior_mean | Needs score-only prior_mean, plus None on excluded days. |
| backend/src/sunday_clays/analytics/insights/streaks.py:_tier_run pf.tier-run (370) | scores | XR | confirmed | run of score >= own_tier | at_least never returns None, so it needs a change. |
| backend/src/sunday_clays/analytics/insights/streaks.py:_three_rising pf.three-rising (469) | scores | XR | confirmed | three consecutive rising scores beating the prior best-of | Indexes days[i-2:i+1] directly. |
| backend/src/sunday_clays/analytics/insights/streaks.py:_podium_run pf.podium-run (593) | scores | CWS | confirmed | run of top-3 finishes |  |
| backend/src/sunday_clays/analytics/insights/sunday.py:_spotlight ev.spotlight (73) | scores | XR | confirmed | residual >= 7 over usual | Auto via residual None. |
| backend/src/sunday_clays/analytics/insights/sunday.py:_rain_day ev.rain-day (219) | scores | MIXED | corrected | wet-Sunday crowd vs dry, played (difficulty), better/steady names (adjusted) | Stale said XR. Crowd/heads UN; played and names XR. Recap email uses only the 'field' variant. |
| backend/src/sunday_clays/analytics/insights/sunday.py:_how_it_played ev.how-it-played (372) | scores | XR | confirmed | difficulty + median | In recap ELIGIBLE. |
| backend/src/sunday_clays/analytics/insights/sunday.py:_toughest_since ev.toughest-since (472) | scores | XR | confirmed | difficulty vs earlier Sundays | Excluded Sundays must also leave the comparison pool. |
| backend/src/sunday_clays/analytics/insights/sunday.py:_week_jump ev.week-jump (562) | scores | XR | confirmed | score jump vs previous Sunday, expected, median | prev may be an excluded day: filter both ends. |
| backend/src/sunday_clays/analytics/insights/sunday.py:_record_watch ev.record-watch (674) | scores | XR | confirmed | club record top score new/tie/near | The running record must skip excluded Sundays. |
| backend/src/sunday_clays/analytics/insights/sunday.py:_top_score ev.top-score (782) | scores | XR | confirmed | Sunday top among the last 3 years' tops |  |
| backend/src/sunday_clays/analytics/insights/sunday.py:_new_faces ev.new-faces (882) | scores | MIXED | confirmed | first-timer count; 'strong' = first round percentile vs earlier first rounds | welcome CWS; strong XR (first_rounds_before pool at 872 too). |
| backend/src/sunday_clays/analytics/insights/sunday.py:_second_visit ev.second-visit (1001) | dates_counts | CWS | confirmed | second appearance within weeks |  |
| backend/src/sunday_clays/analytics/insights/tiers.py:_high_round_count pf.high-round-count (97) | scores | XR | confirmed | count of rounds >= own tier crossing steps | Explicit filter; chart is Explorer COUNT with min_score. |
| backend/src/sunday_clays/analytics/insights/tiers.py:_more_high_rounds pf.more-high-rounds (223) | scores | XR | confirmed | rounds >= tier this year vs last | In recap ELIGIBLE. |
| backend/src/sunday_clays/analytics/insights/tiers.py:_low_end_rising pf.low-end-rising (342) | scores | XR | confirmed | 25th percentile of scores this year vs last |  |
| backend/src/sunday_clays/analytics/insights/trophies.py:_trophy_rare pf.trophy-rare (83) | other | MIXED | confirmed | rarest trophy earned that day from the achievements_awarded table | Follows achievements: class per trophy; uses active_shooter_ids (counts). |
| backend/src/sunday_clays/analytics/insights/trophies.py:_next_trophy pf.next-trophy (202) | both | MIXED | confirmed | rebuilds AchContext from fr frames (incl. fr.stations[STATION_COLUMNS]) and progress for MILESTONE/CALENDAR/CONDITIONS trophies | Mostly CWS; CONDITIONS includes score-based ones (e.g. mudder XR). A dropped column must be in achievements.context.STATION_COLUMNS. |
| backend/src/sunday_clays/analytics/recap_facts.py:FactSource._turnout (267) | dates_counts | UN | new | biggest crowd since / biggest month Sunday | Email 'This week'. |
| backend/src/sunday_clays/analytics/recap_facts.py:FactSource._course_type (305) | other | UN | new | first <round type> course since |  |
| backend/src/sunday_clays/analytics/recap_facts.py:FactSource._course_stations (328) | station_hits | XS | new | toughest/easiest station hit % that day | The dropped station (100%) would be named easiest; must be excluded. |
| backend/src/sunday_clays/analytics/recap_facts.py:FactSource._scores_context (352) | scores | XR | new | middle score highest for the month / since | Skip on excluded day; drop excluded Sundays from the prior pool. |
| backend/src/sunday_clays/analytics/recap_facts.py:FactSource._weather (398) | other | UN | new | coldest/hottest/windiest/wet since |  |
| backend/src/sunday_clays/analytics/recap_facts.py:FactSource._on_this_day (463) | scores | CWS | new | a year ago: shooters and top score | Quotes an official top score in an email with no star mechanism; see open questions. |
| backend/src/sunday_clays/analytics/recap_facts.py:FactSource._year_so_far (477) | dates_counts | CWS | new | rounds this year, steps, passed last year |  |
| backend/src/sunday_clays/analytics/recap_facts.py:FactSource._club_next (518) | dates_counts | CWS | new | club_milestones series (sundays_held, clays_thrown, shooters, rounds) within reach | club_milestones.compute_milestones; clays_thrown is not hits. |
| backend/src/sunday_clays/analytics/recap_facts.py:FactSource._attendance_streak (540) | dates_counts | CWS | new | named N Sundays in a row |  |
| backend/src/sunday_clays/analytics/recap_facts.py:FactSource._station_feats (569) | station_hits | XS | new | named 'broke every target at K of M stations'; 'N shooters broke every target at Station X' | Highest-risk false positive: every shooter is clean on the dropped station. Exclude it from both cleaned and shot counts. |
| backend/src/sunday_clays/analytics/recap_facts.py:FactSource._improvement/_gain (626/617) | scores | XR | new | named mean of last 20 raw scores vs a year ago | Raw Day.score: explicit filter. |
| backend/src/sunday_clays/analytics/recap_facts.py:FactSource._coming_up (648) | dates_counts | CWS | new | N Sundays away from a multiple of 25 appearances |  |
| backend/src/sunday_clays/analytics/recap_insights.py:candidates/_eligible/ELIGIBLE (149/141/65) | scores | MIXED | new | stored Sunday insights eligible for the email (mostly XR kinds) + picking rules | No scoring of its own; inherits kind classes. Most ELIGIBLE kinds are XR, so a dropped Sunday's email thins out. |
| backend/src/sunday_clays/analytics/recap_insights.py:milestone_sentences (292) | scores | CWS | new | pf.targets-milestone facts -> Clays Broken sentences | Official totals. |
| backend/src/sunday_clays/analytics/recap_trophies.py:recap_milestone_items (85) | other | MIXED | new | tiered trophy lines from award codes | Follows achievements; hides station_cleaner, round_score, personal_bests families anyway (HIDDEN_TIER_FAMILIES :41). |
| backend/src/sunday_clays/api/routes/admin_recap.py:get_recap/week_texts (97/75) | both | MIXED | new | RecapOut: shooters, head_count, rounds, This week, milestones, club lines; special -> no insights | No dropped/star field in RecapOut; special Sundays handled at :109-120, :151-155. |
| backend/src/sunday_clays/og/facts.py:facts_for_path (38) | dates_counts | UN | new | link preview: date, shooter count, round type, label | Turned up by the 'facts' grep; outside this lane, no score use. |

Open questions:
- Score streaks (pf.beat-field-streak, pf.above-own-avg-streak, pf.tier-run, pf.three-rising): does an excluded Sunday skip (neither extends nor breaks, run_back None) or break the run? three-rising indexes days[i-2:i+1] directly and needs a decision on whether the three must be consecutive non-excluded Sundays.
- Where to exclude median and difficulty: null event_metrics.median/difficulty for excluded Sundays (fixes ev.how-it-played, toughest-since, week-jump, cl.rain-scores, weather-scoreboard, the recap 'p' flag and recap scores_context on its own, but hides them from the event page), or keep them and add a Sunday.stats_excluded flag checked in each kind?
- Should anchored score kinds on the excluded Sunday itself say nothing (pf.pb, tied-best, first-tier, ev.record-watch, ev.top-score, drought-ended, ev.spotlight), or should CWS-style lines like a 'top score of the day' still name the official score with a star?
- ev.close-finish uses the official top >= 45 gate, and the 'top 3 within one' story includes credited targets. CWS with a star, or suppress on excluded Sundays?
- pf.targets-milestone and the email's 'Clays Broken - N' count the credited (not actually broken) targets under the CWS rule. Confirm the owner is fine with a milestone crossed thanks to credited targets.
- Recap email: RecapOut has no star field and the email has no explainer slot. Should the email carry a one-line note on a dropped-station Sunday? And should on_this_day's 'top score N' a year ago carry a marker when that Sunday had a dropped station?
- Is Day.prior_rounds (used as an eligibility gate: PB needs >= 5 earlier rounds, tier >= 10, and so on) a count of all rounds (CWS) or of score-stat rounds only?
- pf.year-wrapped: the 'sundays' and 'targets' counts are CWS, but 'best' must skip excluded rounds. Can the chart (Explorer avg by month) and the proof check stay consistent once the Explorer excludes those rounds?
- Insight explainer wording: the lints ban 'drop'/'dropped'/'event' in how bullets. Which approved phrase should insight text use (e.g. 'a station thrown out, everyone credited in full')?
- pf.next-trophy and pf.trophy-rare follow the achievements lane. Should CONDITIONS trophies such as mudder (40+ in the rain) be held back on excluded Sundays?

## api

Lane: backend/src/sunday_clays/api/routes/** + explorer/** at sunday-clays-public HEAD 79ee0d8 (verified). Structural facts for the designer:

1) SPECIAL-EVENT PRECEDENT (Plan 17) is the closest existing pattern, and it is implemented as a SQL WHERE, not a flag. analytics/frames.py:132-206: every score frame (load_rounds, load_events, load_station_hits) has `WHERE e.kind = 'regular'`; special Sundays only reach routes through load_calendar (frames.py:313, adds kind/label/target_total), load_appearances (:331), load_special_rounds (:339) and load_special_station_hits (:368). Routes then branch on kind: events.py:401-433 (get_event picks special loaders, _special_results at :218 sets event_rank/percentile/adjusted/expected/residual/mu = None, is_best_round=True, vs_prev=None); club.py:163-195 (counts from calendar/appearances, score numbers from load_rounds); shooters.py:381 (streaks/odometer Sundays from load_appearances); shooters.py:450 /special separate route; insights.py:147 held_dates filters kind=regular; claysmasher.py:43-71 hard-codes `e.kind = 'regular'` in its own SQL; admin_recap.py:109-155 branches on special. A dropped Sunday must NOT copy that WHERE approach: dropped rounds keep rank/wins/podiums/points/appearance counts (CWS) but leave score stats (XR). So load_rounds/load_events need a flag column (e.g. events.stats_excluded threaded into _ROUNDS_SQL/_EVENTS_SQL) and each XR consumer filters on it; filtering the frame centrally would silently break wins/podiums/n_rounds/odometer/club counts that read the same frame.

2) RESPONSE-MODEL PATTERN for the flag: EventSummaryOut (events.py:30), EventDetailOut (:130) and AttendanceOut (club.py:60) already carry kind/label/target_total with `model_config = ConfigDict(json_schema_serialization_defaults_required=True)` so the generated TS schema marks them required. Add `stats_excluded: bool` (or `dropped_stations: list[str]`) the same way. StationLayoutOut (events.py:87) needs `dropped: bool` for the matrix column. Per-round flag candidates: EventResultOut (events.py:54), ShooterRoundOut (shooters.py:118), WinnerOut (:24), PbOut, YirTopRoundOut (yir.py:37), OnThisDayItemOut (yir.py:119), RecordRoundOut (records.py:19), WeatherEventOut (weather.py:20), EventTrendOut (club_insights.py:64), StationEventPctOut (stations.py:60, dropped station rows should just vanish), ExportRound (_claysmasher.py:62).

3) Mixed-count models: ShooterStatsOut (shooters.py:68; used for stats and window_stats) and SplitOut (:162) put n_rounds/n_events (CWS) next to avg/median/best/avg_adjusted (XR), so computing everything over one filtered frame changes n_rounds. The designer has to decide between two n's or a separate `n_excluded`. The same goes for LeaderboardRowOut.n_rounds and min-rounds eligibility (avg boards), and for YirTotalsOut/YirShooterTotalsOut (counts plus avg_score in one model).

4) Explorer (explorer/engine.py): load_explorer_frames (:375) reads fr.load_rounds/load_events/load_station_hits, so it inherits whatever the frames give. Metrics: SCORE/ADJUSTED/RESIDUAL/RATING (AGGREGATED :83) and DIFFICULTY (event metric :143) are XR. ROUNDS/SHOOTERS/WINS/ATTENDANCE are CWS. HIT_PCT (_units :285, joins station_hits to rounds) is XS and also needs the dropped station's rows removed. min_score filter (:220) is a round filter: CWS or XR depending on metric. Filters (spec.py:54) has no exclusion flag. The engine therefore needs a per-metric exclusion inside _units, or a new Filters field. Insight charts store a QuerySpec in InsightChartOut.spec/compare (insights.py:55), so stored insight charts go through /api/explore and will show dropped rounds unless the engine applies the exclusion by default for XR metrics.

5) Admin rule override hook: admin_rules.py:56 accepts any domain/rules.py RuleType (:58: merge_shooter, rename_shooter, score_override, hide_round, round_type_override, set_status, station_reset, alias_name). A new type such as `station_dropped`/`station_not_dropped` would go there with no route change. Every mutation enqueues a rebuild.

6) The ClaySmasher export is now merged at api/routes/claysmasher.py + _claysmasher.py. It is the third copy of the station-hit SQL (_STATIONS_SQL claysmasher.py:53, joins station_layouts), so a layouts.dropped column must be considered there too. The exported station hits include the free credited station and Total Hits = official score. Notes column (_claysmasher.py:118) is the natural place for a 'station N thrown out' note.

7) New since the stale list: /api/shooters/{id}/summary (shooters.py:535 -> analytics/summary.py:82 compute_summary), /api/shooters/{id}/special (:450), /api/club/milestones (club.py:304), /api/leaderboards/movers (leaderboards.py:119), /api/admin/recap/{date} (admin_recap.py:96), og link previews (og.py, counts only), bumps/pageviews/admin_analytics (unaffected). Pure pass-through routes over stored rows (achievements.py, insights.py) depend on the s50/s60 lanes.

| consumer | uses | cls | status | computes | notes |
|---|---|---|---|---|---|
| backend/src/sunday_clays/api/routes/events.py:list_events (176) | scores | MIXED | confirmed | EventSummaryOut per Sunday: counts, median/top_score/difficulty from event_metrics, winners | n_rounds/n_shooters/winners/top_score are CWS (show a star). median/difficulty are XR for trends but are the day's own numbers. EventSummaryOut (:30) needs a stats_excluded/dropped flag in the kind/label/target_total pattern (defaults_required). |
| backend/src/sunday_clays/api/routes/events.py:_winners (163) | scores | CWS | confirmed | event_rank==1 rounds -> WinnerOut | Rank stays on dropped Sundays. WinnerOut (:24) could carry a star flag, or the client can star from the event flag. |
| backend/src/sunday_clays/api/routes/events.py:get_event (391) | both | MIXED | confirmed | EventDetailOut: counts, median/mean/stdev/top/difficulty, results, weather, stations, notables, vs_prev | Already branches special vs regular (:401-433). EventDetailOut (:130) needs a flag and the dropped station label(s) for the * note. Results stay official (CWS). |
| backend/src/sunday_clays/api/routes/events.py:_results (246) | scores | MIXED | new | EventResultOut rows incl. rank, percentile, adjusted, expected, residual, mu_before/after, rating_delta | score/event_rank/percentile/is_best_round CWS. adjusted/expected/residual/rating_delta XR, so they should be null when s10/s30 excludes the round. EventResultOut (:54) could carry a per-round star. _special_results (:218) is the precedent for nulling. |
| backend/src/sunday_clays/api/routes/events.py:_stations (289) | station_hits | CWS | confirmed | StationMatrixOut: layout + per-entry hits + total | Show the matrix as recorded, with the dropped column marked. StationLayoutOut (:87) needs dropped: bool. StationEntryOut.total includes the credited station (equals the official score). |
| backend/src/sunday_clays/api/routes/events.py:event_notables (333) | scores | MIXED | confirmed | PB notables (is_new_pb vs prior max/count) + first-timers | PB is XR: no PB on a dropped day, and dropped rounds must leave out `earlier` max (and n_prior, an open question). first_timer is CWS. Called for special days too, where rounds=regular frame. |
| backend/src/sunday_clays/api/routes/events.py:_vs_prev (371) | scores | MIXED | confirmed | deltas vs previous results_complete regular Sunday: head_count, median, top_score, difficulty | head_count delta CWS. median/top/difficulty deltas XR: skip a dropped prev Sunday, or null the deltas when either side is dropped. Owner choice. |
| backend/src/sunday_clays/api/routes/shooters.py:shooter_stats (193) | scores | MIXED | confirmed | ShooterStatsOut: n_rounds, n_events, avg/median/best score, avg_adjusted, wins, podiums, avg_percentile | avg/median/best/avg_adjusted XR. n_rounds/n_events/wins/podiums CWS. avg_percentile is ambiguous. Used for both stats and window_stats in get_shooter (:363). One model mixes both n's. |
| backend/src/sunday_clays/api/routes/shooters.py:odometer (209) | scores | CWS | confirmed | clays_thrown=rounds*50, clays_broken=sum(score), hit_pct, rounds, Sundays, streaks, favorite month, trophies | Official score includes the free station, so it is cumulative CWS. hit_pct = broken/thrown is ambiguous (inflated). Sundays/streaks come from load_appearances. |
| backend/src/sunday_clays/api/routes/shooters.py:personal_bests (237) | scores | XR | confirmed | overall + per-year best PbOut | Rounds on dropped Sundays are excluded. PbOut (:93). |
| backend/src/sunday_clays/api/routes/shooters.py:splits (297) | scores | XR | confirmed | SplitOut per key: n_rounds, n_events, avg, median, best, avg_adjusted | Same mixed-n issue as ShooterStatsOut. Route get_shooter_splits (:495). |
| backend/src/sunday_clays/api/routes/shooters.py:get_shooter_rounds (418) | scores | CWS | confirmed | ShooterRoundOut list: score, rank, percentile, field_median, adjusted, expected, residual, mu | Rows are listed with a star. field_median/adjusted/expected/residual become null if s10 nulls them. ShooterRoundOut (:118) needs a per-round stats_excluded flag (client pbRoundIds/trend/distribution use this feed). |
| backend/src/sunday_clays/api/routes/shooters.py:get_shooter_rating (470) | scores | XR | confirmed | rating_history points, current/peak mu | Follows s30. Dropped Sundays should add no rating point. |
| backend/src/sunday_clays/api/routes/shooters.py:list_shooters (320) | dates_counts | CWS | new | directory n_rounds/n_events, active (active_shooter_ids), latest mu | Counts CWS. mu follows s30 (XR upstream). |
| backend/src/sunday_clays/api/routes/shooters.py:get_shooter_summary (535) -> analytics/summary.py:compute_summary (82) | scores | MIXED | new | summary card: sundays, special_sundays, rounds, average, best, pbs_set, trophies, longest_streak | average/best/pbs_set (_pbs_set :68, is_new_pb) XR. sundays/rounds/trophies/streak CWS. ShooterSummaryCardOut (:515), feature-gated summary_card. |
| backend/src/sunday_clays/api/routes/shooters.py:get_shooter_special (450) | scores | UN | new | special-Sunday rounds list | Special only. A dropped station on a special Sunday is out of scope. |
| backend/src/sunday_clays/api/routes/club.py:club_summary (151) | scores | MIXED | confirmed | ClubSummaryOut: event/round/shooter counts, avg/median/top score, n_perfect, clays thrown/broken, head counts, status_by_year | Counts/clays/status_by_year CWS. avg/median/top/n_perfect XR (scores = rounds['score'] :177). One rounds frame feeds both. |
| backend/src/sunday_clays/api/routes/club.py:score_distribution (126) / club_distribution (240) | scores | XR | confirmed | per-year mean/median/percentiles/histogram | DistributionOut (:88). |
| backend/src/sunday_clays/api/routes/club.py:club_first_rounds (257) -> analytics/cohorts.py:first_round_scores (102) | scores | XR | confirmed | histogram of each shooter's first-Sunday best score | Open question: if the first Sunday is dropped, skip the shooter or not. The 'first' date should stay the real first date. |
| backend/src/sunday_clays/api/routes/club.py:club_attendance (198) | dates_counts | CWS | new | AttendanceOut per Sunday incl. special | Counts only. Could carry the same flag as EventSummaryOut (AttendanceOut :60 uses the defaults_required pattern). |
| backend/src/sunday_clays/api/routes/club.py:club_cohorts (217) | dates_counts | CWS | new | cohort retention from appearances | Appearances only. |
| backend/src/sunday_clays/api/routes/club.py:get_club_milestones (304) -> analytics/club_milestones.py | dates_counts | CWS | new | club milestones: sundays_held, clays_thrown, shooters, rounds | Cumulative counts. Feature-gated club_milestones. |
| backend/src/sunday_clays/api/routes/club_insights.py:get_regulars (88) / get_conversion (102) | dates_counts | CWS | confirmed | core/lapsed regulars, guest conversion | Counts only. |
| backend/src/sunday_clays/api/routes/club_insights.py:get_parity (110) | scores | CWS | confirmed | distinct winners, top3 share, favorite win rate | Uses ranks. |
| backend/src/sunday_clays/api/routes/club_insights.py:get_trends (118) | scores | MIXED | corrected | yearly_trends (counts), event_trends (top/median/difficulty + rolling8), seasonality (calendar head counts) | years CWS. events XR: drop the Sunday from the rolling8 series, and EventTrendOut (:64) has no flag. seasonality now takes load_calendar (:137, 'Sundays and head counts'). Check whether MonthTrendOut.mean_median (:78) is still computed there (XR if so). |
| backend/src/sunday_clays/api/routes/stations.py:get_stations (264) | station_hits | XS | confirmed | stations_overview: hit_pct/CI/deff/clean_rate/separator/leaders, by_event, shooter matrix | Comes from st.load_station_frame. The dropped station rows have to be removed there (analytics/stations.py). |
| backend/src/sunday_clays/api/routes/stations.py:_coverage (241) | dates_counts | UN | confirmed | station Sundays, date span, scored Sundays, latest_date | A dropped Sunday still has a sheet. Open: does a Sunday where every station was dropped still count? |
| backend/src/sunday_clays/api/routes/stations.py:get_station (320) | station_hits | XS | confirmed | station_detail: eras, by_event, leaders, wind x station | 404 check at :332 uses frame station_label. If dropped rows are filtered upstream, a label only ever seen dropped (e.g. 7A) would 404. |
| backend/src/sunday_clays/api/routes/stations.py:get_shooter_stations (377) | station_hits | XS | confirmed | shooter_station_deltas + coverage (rounds/Sundays) | Coverage counts are UN. |
| backend/src/sunday_clays/api/routes/leaderboards.py:get_leaderboard (53) -> analytics/leaderboards.py:leaderboard_for | scores | MIXED | confirmed | one board per metric: avg_score, avg_adjusted, best_score, rating_gain (XR); wins, podiums, events, rounds, season_points (CWS) | Route is pass-through. LeaderboardRowOut.n_rounds (:36) and min_rounds eligibility on avg boards need the stats-eligible count. event_dates (leaderboard_event_dates, has_scores dates) is CWS. |
| backend/src/sunday_clays/api/routes/leaderboards.py:get_rating_movers (119) | scores | XR | new | rating_gain board as climbers | Follows the s30 rating. |
| backend/src/sunday_clays/api/routes/leaderboard_history.py:get_leaderboard_history (48) -> analytics/leaderboard_history.py | scores | MIXED | confirmed | race frames per metric (default season_points) | Class per metric, same as the leaderboards. Race/season_points is CWS. |
| backend/src/sunday_clays/api/routes/records.py:get_records (91) -> analytics/records.py:records_for | scores | MIXED | confirmed | highest_scores, perfect_rounds, biggest_adjusted, biggest_jumps, highest_ratings (XR); most_events, longest_streaks (CWS) | Pass-through. Jumps need from/to rounds both non-excluded (or skip over a dropped Sunday). The totals/tied_more counts follow. |
| backend/src/sunday_clays/api/routes/yir.py:yir_club (135) -> analytics/yir.py:club_year | scores | MIXED | confirmed | totals (counts, clays, avg_score), newcomers, perfect_rounds, top_rounds, busiest/hardest/easiest, trophies, months avg, previous | Counts/clays/busiest/trophies CWS. avg_score/perfect/top_rounds/hardest/easiest/month avg XR. YirTotalsOut (:26) mixes them. |
| backend/src/sunday_clays/api/routes/yir.py:yir_shooter (146) -> analytics/yir.py:shooter_year | scores | MIXED | confirmed | totals, best, wins, podiums, best_finish, pbs, trophies, rating start/end, attendance_rank, months | best/pbs/avg/rating/month avg (club_avg_score too) XR. wins/podiums/best_finish/attendance_rank/counts CWS. |
| backend/src/sunday_clays/api/routes/yir.py:on_this_day (161) -> analytics/yir.py:on_this_day | scores | CWS | confirmed | past Sundays on this date: head_count, n_shooters, top_score, median, winners | Official results with a star. OnThisDayItemOut (:119) needs a flag. median is ambiguous. |
| backend/src/sunday_clays/api/routes/weather.py:weather_events (125) -> analytics/weather_effects.py:weather_events | scores | MIXED | confirmed | WeatherEventOut per event: median, mean, top_score, difficulty + weather + bands | Counts CWS. median/mean/top/difficulty XR for weather charts: exclude the event or add a flag to WeatherEventOut (:20). |
| backend/src/sunday_clays/api/routes/weather.py:weather_effects_route (132) | scores | XR | confirmed | club weather model fit + band mean_score/mean_difficulty | WeatherBandOut.n_rounds/n_events follow the exclusion. |
| backend/src/sunday_clays/api/routes/weather.py:weather_sensitivity (150) | scores | XR | confirmed | per-shooter weather sensitivity betas |  |
| backend/src/sunday_clays/api/routes/weather.py:weather_turnout (160) | dates_counts | UN | confirmed | head_count by weather band |  |
| backend/src/sunday_clays/api/routes/predictions.py:next_sunday (61) -> analytics/predictions.next_predictions | scores | MIXED | confirmed | predicted difficulty, field median, expected scores (skill), attend_prob, expected turnout | difficulty/field_median/expected/sd XR (skill + weather model). attend_prob/turnout UN. |
| backend/src/sunday_clays/api/routes/shooter_insights.py:get_shooter_insights (60) -> analytics/profile.py:shooter_insights | scores | MIXED | confirmed | floor/ceiling, bad_day_rate, form, wins, podiums, avg_percentile, peak_mu, learning_curve, rust, milestone | floor/ceiling/bad_day/form/learning/rust/peak XR. wins/podiums/milestone CWS. avg_percentile ambiguous. n_rounds/recent_n follow. |
| backend/src/sunday_clays/api/routes/achievements.py:list_achievements (193) / get_achievement (217) / get_event_achievements (314) | other | UN | new | reads stored achievements_awarded, holder counts, rarity | Pass-through. Correctness depends on s50 award rules (other lane). TrophyAwardOut.details (:72) may hold score values. |
| backend/src/sunday_clays/api/routes/achievements.py:get_shooter_achievements (251) | both | MIXED | new | earned trophies + progress(cached_context) tier progress | progress comes from achievements/context.py cached_context (mixed cum counts CWS / prior_best XR / station XS), so it must match the s50 rules. |
| backend/src/sunday_clays/api/routes/insights.py:held_dates (147) + feeds (196-294) | other | UN | new | stored insight feeds; reference Sunday = last results_complete regular Sunday | Pass-through of stored insights (s60 lane). A dropped Sunday stays a held Sunday (correct for CWS). InsightChartOut.spec/compare (:59,:66) are QuerySpecs run through /api/explore, so the explorer must apply the exclusion for XR metrics or the charts disagree with the text. |
| backend/src/sunday_clays/api/routes/admin_recap.py:get_recap (96) / week_texts (75) | both | MIXED | new | recap email: shooters/head_count/rounds, stored 'This week' insights + recap facts, clays-broken milestone sentences, trophy lines, club milestones, special top_score | Counts/clays-broken/trophies/club milestones CWS. Insights and recap_facts (analytics/recap_facts.py FactSource over s60 build_frames) follow the insight rules. Open: should the email note the dropped station? |
| backend/src/sunday_clays/api/routes/claysmasher.py:get_claysmasher_export (139) / _rounds (74) / _STATIONS_SQL (53) | both | CWS | corrected | zip of ClaySmasher CSVs: official score, Total Targets, per-station hits/targets | Merged now (the stale list called it an unmerged branch). Exports official scores and the credited station as recorded. It is the third copy of the station SQL. Option: annotate in _notes (_claysmasher.py:118) or export the dropped flag. |
| backend/src/sunday_clays/explorer/engine.py:_units (274) / run_query (320) | both | MIXED | confirmed | SCORE/ADJUSTED/RESIDUAL/RATING aggregates (XR), DIFFICULTY event metric (XR), ROUNDS/SHOOTERS/WINS/ATTENDANCE (CWS), HIT_PCT station join (XS) | Needs per-metric exclusion: XR metrics drop flagged rounds/events, HIT_PCT drops dropped-station rows (:285-294), counts keep them. n_rounds in QueryResult follows. No Filters field today (spec.py:54). |
| backend/src/sunday_clays/explorer/engine.py:_filter_rounds min_score (212) | scores | AMBIGUOUS | confirmed | rounds >= min_score filter | With ROUNDS/SHOOTERS/WINS it is a count over official scores (CWS). With SCORE it is XR. Insight charts use min_score. |
| backend/src/sunday_clays/explorer/engine.py:load_explorer_frames (375) | both | MIXED | new | cached rounds/events/station_hits frames from analytics.frames | Central hook: carry the flag columns through here. Memoised on data_version. |
| backend/src/sunday_clays/api/routes/admin_rules.py:add_rule (56) | other | UN | new | creates overlay rules of any domain/rules.py RuleType + enqueues a rebuild | Hook for a manual dropped-station override rule type (RuleType enum domain/rules.py:58). No route change needed beyond the payload model. |
| backend/src/sunday_clays/api/routes/meta.py:get_meta (50) | dates_counts | UN | new | event/round/station-event counts, date range |  |
| backend/src/sunday_clays/api/routes/og.py:_page (39) / og_sunday_image (60) -> og/facts.py:facts_for_path (38) | dates_counts | UN | new | link-preview facts: date, shooter count, round type, special label | No scores in previews. |

Open questions:
- Event-day median/mean/stdev/difficulty on EventDetailOut/EventSummaryOut: show them for the dropped Sunday itself (with the star), or null them? The free station inflates them, and the same numbers feed trends (club_insights.event_trends, weather_events).
- vs_prev: when this Sunday or the previous one is dropped, should the comparison skip to the last non-dropped Sunday, or should the score deltas be null?
- PB rules (events.event_notables, summary._pbs_set, personal_bests): should rounds on dropped Sundays still count toward PB_MIN_PRIOR_ROUNDS (n_prior), even though their scores are excluded from the prior max?
- first_round_scores: if a shooter's first Sunday is dropped, leave the shooter out of the first-round histogram, or use their next Sunday?
- ShooterStatsOut/SplitOut/LeaderboardRowOut/YIR totals: should n_rounds stay the official count, become the stats-eligible count, or should both be exposed? This also decides leaderboard min-rounds eligibility.
- Odometer hit_pct (clays_broken/clays_thrown): keep it over official scores (CWS, slightly inflated) or exclude the dropped station?
- Explorer: should XR metrics always exclude dropped Sundays server-side (so stored insight charts match), or should there be an opt-in Filters flag?
- If a station label only ever appears as dropped (e.g. a one-off 7A), should /api/stations/{label} 404 or show an empty or explained page?
- ClaySmasher export: should the export carry a note or flag for the thrown-out station, or export it exactly as recorded?

## frontend

Frontend lane checked against frontend/src (HEAD 79ee0d8). Read-only; I ran no git write commands.

STRUCTURAL FACTS FOR THE DESIGNER
1. Explainers. There are 15 files, features/*/explainers.ts. They type against components/charts/types.ts:36 (Explainer has what/read/computed/scope/terms/noTerms) and render through components/ui/Explainer.tsx and AboutBlock. Insight explainers are not frontend copy: they come from the backend as insight.how and insight.how_you, rendered by features/insights/components/InsightExplainer.tsx:7. Three explainers are built at run time from parts:
   - leaderboards/explainers.ts boardExplainer:139, from METRIC_COMPUTED:8, CUSTOM_EXTRA:77, CUSTOM_REPLACE:86 and AVERAGE_QUALIFY:61.
   - explorer/explainers.ts explorerExplainer:116, from METRIC_COPY:12.
   - records recordsExplainer:67 and race raceExplainer:50. These two take no metric, so race copy cannot say which measure drops the rounds.
   Shared-constant pattern: stations/explainers.ts:3-7 (SHEETS_ONLY, WINDOW, LETTERED) and leaderboards/explainers.ts:5 (FILTERS_APPLY, WINDOW_LINE:69). The cleanest disclosure is a DROPPED constant in the same style, plus a parallel one for excluded rounds.
2. Glossary coupling. glossary/terms.ts:2-17 holds the GlossaryTermId union and GLOSSARY_TERMS. glossary/triggers.ts:10 maps each term to a regex. glossary/explainerLint.test.ts:49 and :65 fail any static or run-time-built explainer whose text matches a trigger without listing the term. If a 'dropped-station' term is added (model it on 'special-shoot', terms.ts:92), every explainer that mentions it must list it in terms.
3. Explainer test limits:
   - Word caps of 95 per key apply to events, home and admin-analytics: events/explainers.test.ts:43-48, home/explainers.test.ts:49-53, admin-analytics:72-74. My approximate counts leave little room: events difficulty about 95 (none), stn 87, results 88, calendar 89, weather 80, vsPrev 77, special 73; home meLast 93, pulse 92, meOdometer 84.
   - Banned words: test/language.ts:5 BANNED_WORDS (he/she/class). events, home, shooters and stations also ban 'event'/'events' (stations bans 95%/CI too). shooters bans percentile/residual. club bans residual/percentile/parity. weather bans worse/worst/bad/poor/weak/struggle. predictions bans you/your.
   - Pinned strings and counts:
     - records/explainers.test.ts:49 pins computed.length = base + 1.
     - leaderboards test :42 pins lb-chart computed[0] exactly, and :49-94 pins substrings.
     - club test :104 needs 'The round-type filter does not apply.'.
     - weather :25 needs 'The round-type filter applies.'.
     - stations :32 needs /only Sundays with a station sheet/ and :63 needs /inside the time window you picked/.
     - shooters :46-63 pins substrings of rating/trend/finishes/cal.
     - home :65-68.
     - summary :8 pins the terms array exactly.
     - club :82/:88 pin the terms arrays of club-milestone and ctot exactly.
     - events/home/admin-analytics tests also require an explainer for every urlKey in the feature (events test :20-32).
4. Markers already in use:
   - PbTable '(early)': shooters/components/PbTable.tsx:63-68. It is an aria-hidden glyph plus an sr-only sentence, with a legend line at :78-80.
   - R2 badge: events/components/ResultsTable.tsx:98-105, a bordered span with a title attribute.
   - Partial-results banner: events/pages/EventDetailPage.tsx:111-115, p role=note with border-accent. SPECIAL_NOTE is at :53 and is rendered the same way at :61.
   - Header round-type source note: SOURCE_NOTES at EventDetailPage.tsx:40, rendered at :217.
   - Calendar legend: events/components/SeasonCalendar.tsx:12-26 (CELL_STYLES and LEGEND).
   - Special tags: events/format.ts:62-87 (isSpecial, specialTag 'Special · 60', specialLine).
   - Muted note: stations/CoverageNote.tsx:38.
   - Warning: '★' already means 'special shoot' in the shooter calendar (shooters/explainers.ts:95, ProfileCharts.tsx:451). A '*' for dropped-station Sundays sitting next to '★' could be misread, so the glyph and wording need care.
5. The UI cannot detect dropped-station Sundays today. No flag exists on EventSummaryOut, EventDetailOut, EventResultOut, ShooterRoundOut or StationLayoutOut. A designer needs events.stats_excluded (or similar) on EventSummary, EventDetail and ShooterRound, and a dropped flag on StationLayoutOut. Every * spot and every client-side exclusion (ClubPulse high, PB pins, trend lines, distribution, PbTable early count, weather wind rose and conditions) depends on it.
6. Client code treats field_median and percentile being null as 'partial results'. MePanel.tsx:32-37 uses field_median === null to show a rating move of '—'. shooters/charts.ts:215 isFinish uses percentile !== null to mean a full-results Sunday. If the backend nulls field_median or adjusted on excluded Sundays (the v0 proposal), MePanel will make the Sunday look partial. Keep percentile, or Finishes drops CWS Sundays.
7. Special shoots in the UI today:
   - They are a separate kind, checked with isSpecial (events/format.ts:63). Payload fields are kind, label and target_total.
   - EventDetailPage branches to SpecialEvent (:56). It shows SPECIAL_NOTE, a SpecialResultsTable with no rank or rating, and hides the VsPrev card (:236).
   - LatestEventCard has SpecialLatest (:28), and EventShareCard has SpecialShareCard (:51).
   - SeasonCalendar shows a 'special' cell state.
   - Shooter specials come from a separate endpoint, /api/shooters/{id}/special (shooters/api.ts:120-130). They are drawn as '★' cells or counted in monthsModel. /rounds returns regular rounds only, so the client never sees special scores in its stats.
   - heldDates excludes specials (shooters/api.ts:104). admin-recap/format.ts:51 and RecapPage.tsx:68 branch on kind.
   - In short, specials are excluded by the server not sending them in score payloads. For dropped-station Sundays the rounds stay in /rounds (they count as official), so the client needs a per-round flag.
8. API types and mocks:
   - frontend/src/api/schema.d.ts is generated by `pnpm gen:api` (package.json:14; it also runs as pretypecheck) from ../openapi.json via sunday_clays.api.export_openapi. Both files are gitignored (.gitignore:28-29).
   - The local copy dated Sep 30 is STALE: its EventSummaryOut and EventDetailOut lack kind, label and target_total, which backend api/routes/events.py:49-51 and :154 send. Regenerate it before designing.
   - Feature api.ts files derive types with JsonOf<paths[...]>.
   - MSW: test/msw/handlers.ts globs features/*/mocks.ts handlers. Mocks are typed object literals (for example events/mocks.ts:35 eventSummaries: EventSummary[], :149 eventDetail, :335/:393 special fixtures), so a new required response field means updating every fixture literal.
   - Coverage floor is 90% lines and branches (vitest.config.ts:26). Ratchets live at repo root, ratchets/baseline.json and budgets.json.
9. Rule conflicts in copy:
   - YIR 'Average score: clays broken divided by rounds' (yir/explainers.ts:16 and :53, glance and shooterYear). Clays broken is CWS and average is XR, so this definition breaks and must be reworded.
   - The same pattern is in shooters odometer (:211, hit rate = broken ÷ thrown) and club stat-clays.
   - summary-card copy (summary/explainers.ts:8) groups rounds, average, best and PBs together, but they now split: rounds CWS, the rest XR.

| consumer | uses | cls | status | computes | notes |
|---|---|---|---|---|---|
| frontend/src/features/events/explainers.ts:calendar (9) | dates_counts | CWS | confirmed | Sunday calendar states | 89 words. A legend state for dropped-station Sundays could go here; the 95-word cap applies. |
| frontend/src/features/events/explainers.ts:stn (23) | station_hits | XS | confirmed | per-Sunday station hit heatmap | Needs a line saying the dropped column is marked/credited. About 87 words, 8 left. |
| frontend/src/features/events/explainers.ts:results (35) | scores | MIXED | confirmed | ranked official scores, vs middle score, rating change | Rank and score are CWS with *. Vs middle score and rating change are XR, shown as '—'. Needs a disclosure. About 88 words, so it must be tight. |
| frontend/src/features/events/explainers.ts:median (61) | scores | CWS | confirmed | day median | That day's official figure with *. Trend consumers exclude it. |
| frontend/src/features/events/explainers.ts:topScore (69) | scores | CWS | confirmed | day top score | With *. |
| frontend/src/features/events/explainers.ts:difficulty (73) | scores | XR | confirmed | day difficulty vs ratings | About 95 words, no room left. Adding a disclosure means rewriting the entry. |
| frontend/src/features/events/explainers.ts:vsPrev (97) | scores | AMBIGUOUS | confirmed | deltas vs previous full-results Sunday | Should a dropped Sunday be skipped as 'previous', and should its own deltas show? About 77 words. |
| frontend/src/features/events/explainers.ts:notables (110) | other | UN | confirmed | notables list | PB and first-timer are told by insights. |
| frontend/src/features/events/explainers.ts:shooters/headCount/stations/weather/special (47,54,116,86,120) | dates_counts | UN | confirmed | counts / weather / special rule | special is the copy model for a dropped-station rule explainer (73 words). |
| frontend/src/features/stations/explainers.ts:SHEETS_ONLY/WINDOW/LETTERED (3-7) | station_hits | XS | confirmed | shared disclosure constants | Pattern for adding a DROPPED constant to every stations entry. The test requires the sheet line (:32). |
| frontend/src/features/stations/explainers.ts:station-summary,sthit,sttime,stmatrix,stera,stwind,station-leaders,stdelta,stdelta-table (15,32,49,65,81,96,112,126,142) | station_hits | XS | confirmed | hit %, clean rate, separator, trends, matrix, setups, wind, leaders, vs field | All need the disclosure. No word cap. Bans 'event', '95%' and 'CI'. |
| frontend/src/features/shooters/explainers.ts:rating (8) | scores | XR | confirmed | skill rating line | Needs a disclosure. Test pins a substring (:46). |
| frontend/src/features/shooters/explainers.ts:trend (22) | scores | XR | confirmed | every round, vs middle, PB pins, roll10/roll20/so_far/pb lines | Says 'Every round you shot', but excluded rounds must not feed PB pins or the lines. Decide whether they are still plotted with * or hidden. |
| frontend/src/features/shooters/explainers.ts:finishes (37) | scores | CWS | confirmed | place per full-results Sunday | Depends on percentile staying non-null (charts.ts:215). |
| frontend/src/features/shooters/explainers.ts:dist,learn,splits,tough-days (47,61,75,119) | scores | XR | confirmed | score distribution, learning curve, split averages, vs field by difficulty | dist says 'Every round counts, including ... incomplete results', so the wording must change. |
| frontend/src/features/shooters/explainers.ts:cal (90) | both | CWS | confirmed | calendar coloured by best score | '★' is already the special-shoot glyph here, so a * for dropped Sundays would sit next to it. The cell colour comes from the official score. |
| frontend/src/features/shooters/explainers.ts:cal-month,hero-rounds,hero-sundays,win-rounds,milestone,wins (106,134,142,178,306,256) | dates_counts | CWS | confirmed | counts of Sundays/rounds/wins | No change needed beyond the *. |
| frontend/src/features/shooters/explainers.ts:hero-average,hero-median,hero-best,win-average,win-best,pbs (150,160,169,186,198,318) | scores | XR | confirmed | avg/median/best, PBs | Each needs a disclosure. Wording such as 'All your scores added up' becomes wrong. |
| frontend/src/features/shooters/explainers.ts:odometer (204) | scores | MIXED | confirmed | clays thrown/broken, hit rate, streaks | Clays broken is CWS. Hit rate = broken ÷ thrown is ambiguous. |
| frontend/src/features/shooters/explainers.ts:floor-ceiling,bad-day,form,peak,rust (218,230,244,279,292) | scores | XR | confirmed | form/expected-score stats | floor-ceiling says 'Every round counts'. |
| frontend/src/features/shooters/explainers.ts:field-beaten (267) | scores | AMBIGUOUS | confirmed | avg percentile | Placings count (CWS), but it reads as a performance stat. |
| frontend/src/features/club/explainers.ts:club-milestone,club-milestones,ctot (11,21,32) | dates_counts | CWS | new | cumulative clays/rounds/Sundays | Club milestones (Plan 19). Terms arrays are pinned in the test (:82,:88). |
| frontend/src/features/club/explainers.ts:att,season,turnout,new,ret,status,conv (48,77,92,152,166,181,195) | dates_counts | UN | confirmed | turnout/cohorts/status |  |
| frontend/src/features/club/explainers.ts:years,stat-sundays,stat-shooters,stat-rounds,stat-clays,stat-first,regulars-core,regulars-lapsed (63,227,239,252,262,272,284,296) | dates_counts | CWS | confirmed | counts and clays broken | stat-clays is the sum of official scores. |
| frontend/src/features/club/explainers.ts:dist,scores,diff,first-rounds (107,123,137,306) | scores | XR | confirmed | yearly distribution, median/top trend, difficulty trend, first-round scores | All need a disclosure. |
| frontend/src/features/club/explainers.ts:parity (210) | scores | AMBIGUOUS | confirmed | win spread; favorite by rating | Wins are CWS. The favorite comes from the rating, which is XR. |
| frontend/src/features/home/explainers.ts:pulse,pulseTurnout,latestShooters (9,32,50) | dates_counts | UN | confirmed | turnout | pulse is about 92 words. |
| frontend/src/features/home/explainers.ts:pulseHeld (23) | dates_counts | CWS | confirmed | full-results Sundays |  |
| frontend/src/features/home/explainers.ts:pulseHigh (41) | scores | XR | confirmed | window high score | Computed client-side in ClubPulse.pulseStats. Needs a flag on EventSummary. |
| frontend/src/features/home/explainers.ts:latestMedian,latestTop (58,66) | scores | CWS | confirmed | latest Sunday median/top | With *. |
| frontend/src/features/home/explainers.ts:meLast (74) | scores | MIXED | confirmed | last score, finish, rating move | Score and finish are CWS. Rating move is XR. Copy says '—' means partial; about 93 words. |
| frontend/src/features/home/explainers.ts:meOdometer (87) | scores | CWS | confirmed | clays broken, Sundays, streak |  |
| frontend/src/features/leaderboards/explainers.ts:METRIC_COMPUTED avg_score,avg_adjusted,best_score,rating_gain (9,13,17,37) + CUSTOM_EXTRA (77) + CUSTOM_REPLACE.rating_gain (95) | scores | XR | confirmed | average/adjusted/best/rating gain | The disclosure goes into these arrays and appears in boardExplainer. Leaderboard tests pin substrings, not full arrays. |
| frontend/src/features/leaderboards/explainers.ts:METRIC_COMPUTED wins,podiums,events,rounds,season_points (21,25,29,33,41) | dates_counts | CWS | confirmed | counts/points |  |
| frontend/src/features/leaderboards/explainers.ts:lb-chart (107), lb-movers (119) | scores | MIXED | confirmed | top ten bars; rating climbers | lb-chart is generic, with computed[0] pinned. lb-movers is XR. |
| frontend/src/features/race/explainers.ts:race-bars,race-bump (13,26), raceExplainer (50) | both | MIXED | confirmed | replay of the leaderboard for the chosen metric | Race metrics include avg_score, avg_adjusted, best_score and rating_gain (race/labels.ts:30-40), but raceExplainer takes no metric, so it cannot disclose per metric. |
| frontend/src/features/records/explainers.ts:rec-events,rec-streaks (17,31) | dates_counts | CWS | confirmed | most Sundays, streaks |  |
| frontend/src/features/records/explainers.ts:rec-highest (46) | scores | XR | confirmed | highest rounds | Says 'Every round counts'. Test pins computed.length = base + 1 (:49 for rec-events only). |
| frontend/src/features/records/components/RecordSections.tsx:BiggestAdjusted/BiggestJumps/HighestRatings/PerfectRounds (326,346,366,387) | scores | XR | new | records with subtitle text only | No explainer object. The disclosure must go in the subtitle strings (:335,:355,:375,:399). |
| frontend/src/features/explorer/explainers.ts:METRIC_COPY score,adjusted,residual,rating,difficulty (13,24,36,48,101) | scores | XR | confirmed | explorer score metrics | score says 'every round'. |
| frontend/src/features/explorer/explainers.ts:METRIC_COPY rounds,shooters,attendance,wins (59,67,72,83) | dates_counts | CWS | confirmed | counts |  |
| frontend/src/features/explorer/explainers.ts:METRIC_COPY hit_pct (91) | station_hits | XS | confirmed | hit % |  |
| frontend/src/features/explorer/explainers.ts:CHOICES_EXPLAINER (146) | other | AMBIGUOUS | confirmed | query choice notes incl. minimum score | min_score filter (FilterControls.tsx:176): decide whether excluded rounds pass it. |
| frontend/src/features/weather/explainers.ts:wf,wr,wb,ws,conditions,profile-sensitivity (10,27,41,71,88,101) | scores | XR | confirmed | difficulty vs weather, median by wind, band averages, sensitivities | Tests pin 'The round-type filter applies.' and ban negative words. |
| frontend/src/features/weather/explainers.ts:wt (56) | dates_counts | UN | confirmed | turnout by weather |  |
| frontend/src/features/yir/explainers.ts:glance,shooterYear (8,47) | scores | MIXED | confirmed | counts, clays broken, average = clays broken ÷ rounds | The average-from-clays-broken definition conflicts with CWS clays and XR average. Reword. |
| frontend/src/features/yir/explainers.ts:highlights,leaders,clubMonths,shooterBest (19,29,37,58) | scores | MIXED | confirmed | top round/perfect/hardest-easiest; leaders; monthly rounds+avg; best/wins/PBs | Counts, wins, busiest and trophies are CWS. Top, perfect, hardest/easiest, avg and PBs are XR. |
| frontend/src/features/yir/explainers.ts:shooterMonths (66) | scores | XR | confirmed | monthly avg vs club |  |
| frontend/src/features/yir/explainers.ts:onThisDay (76) | scores | CWS | confirmed | past Sunday winners/top | With *. |
| frontend/src/features/predictions/explainers.ts:next-sunday (8) | scores | XR | confirmed | expected scores from skill + weather model | Test bans you/your. |
| frontend/src/features/achievements/explainers.ts:trophy-progress,next-trophy (48,59) | scores | MIXED | confirmed | tier progress incl. clays broken, best round | Clays broken and Sundays are CWS. The best-round family is XR. |
| frontend/src/features/achievements/explainers.ts:rarity,holders,trophytl (7,22,35) | other | UN | new | trophy holder counts |  |
| frontend/src/features/summary/explainers.ts:summary-card (4) | scores | MIXED | new | window Sundays/rounds/avg/best/PBs/streak | Line :8 groups rounds/average/best/PBs, which now split (rounds CWS, rest XR). Test pins terms exactly. |
| frontend/src/features/admin-analytics/explainers.ts:visitors,pages,bumps,uptake (9-50) | other | UN | new | site analytics |  |
| frontend/src/features/glossary/terms.ts:GLOSSARY_TERMS (26) + triggers.ts:GLOSSARY_TRIGGERS (10) + explainerLint.test.ts (49,65) | other | UN | new | glossary terms and lint | Adding a 'dropped-station' term means extending the union, a trigger regex and terms on every matching explainer. The special-shoot term (:92) is the model. |
| frontend/src/features/events/pages/EventDetailPage.tsx:ScoredEvent (105) | scores | CWS | confirmed | header stats + partial banner + results | Banner pattern at :111-115 and SPECIAL_NOTE at :53/:61. The header source note (:40,:217) is a place for '* Station N thrown out'. |
| frontend/src/features/events/components/ResultsTable.tsx:ResultsTable (38) | scores | CWS | confirmed | rank, score, adjusted, rating delta | Score cell is :107. R2 badge pattern :98-105. adjusted :108 and ratingDelta :29 would be '—' (XR). |
| frontend/src/features/events/charts.ts:stationMatrixModel (46) | station_hits | XS | confirmed | station table/heatmap columns, total, score | Column label 'Stn X (n)' at :54 is where to mark the dropped column. Station total :63 vs Score :64. |
| frontend/src/features/events/components/EventList.tsx:summaryLine (13) | scores | CWS | confirmed | 'n shooters · type · median · top' | Spot for *. Special branch at :14. |
| frontend/src/features/events/components/SeasonCalendar.tsx:cellState/cellLabel/LEGEND (29,46,20) | dates_counts | CWS | confirmed | calendar cell state | Add a legend state or aria text. CELL_STYLES at :12. |
| frontend/src/features/events/components/VsPrevCard.tsx:VsPrevCard (10) | scores | AMBIGUOUS | confirmed | deltas from server vs_prev | Hidden for specials (EventDetailPage :236). |
| frontend/src/features/events/components/NotablesCard.tsx:NotablesCard (12) | other | UN | corrected | filters out pb/first_timer | Renders only unknown kinds today. PBs moved to insights, so no * spot here. |
| frontend/src/features/events/components/SpecialResultsTable.tsx (9), SpecialShootsCard.tsx (13) | scores | UN | new | special results 'x of total' | Plan 17 special-shoot UI. Model for 'not ranked or rated' copy. |
| frontend/src/features/home/components/LatestEventCard.tsx:LatestEventBody (53) | scores | CWS | confirmed | winners (:14), median, top | * spot at :83-100. SpecialLatest branch at :28. |
| frontend/src/features/home/components/ClubPulse.tsx:pulseStats (21) | scores | XR | confirmed | seasonHigh = max top_score across window events (client) | Computed in the browser. Needs an excluded flag on EventSummary to skip. held/avgTurnout are CWS/UN. |
| frontend/src/features/home/components/MePanel.tsx:lastResult (26) | scores | MIXED | confirmed | best round on last date, rank, rating move | Uses field_median===null to mean partial (:32-37). Score/rank shown at :57 (* spot). |
| frontend/src/features/share/components/EventShareCard.tsx:EventShareCard (11) | scores | CWS | confirmed | top 5 by rank, median | An image card needs a * plus a footnote. |
| frontend/src/features/share/components/ProfileShareCard.tsx (6) | scores | XR | new | overall PB from server pbs | Server-side PB. |
| frontend/src/features/summary/format.ts:summaryLines (10) | scores | MIXED | new | Sundays, rounds·average, best, PBs, streak from server summary | 'Rounds · Average' sits on one line (:17), so the counts would differ. |
| frontend/src/features/shooters/components/PbTable.tsx:PbTable/isEarly (29,33) | scores | XR | confirmed | PB rows; early = roundsBefore < 5 (client) | Marker pattern at :63-68 and legend at :78-80. Open question: should excluded rounds count toward the 5 earlier rounds? |
| frontend/src/features/shooters/charts.ts:pbRoundIds (81) | scores | XR | confirmed | PB pins (client) | Must skip excluded rounds. |
| frontend/src/features/shooters/charts.ts:trendLineByDate (117), trendModel (142) | scores | XR | confirmed | roll10/roll20/so_far/pb lines; per-round plot | Client-side. Mirrors the insight engine rule (spec §3.6), so the backend and client must exclude identically. |
| frontend/src/features/shooters/charts.ts:distributionModel (265) | scores | XR | confirmed | your score shares (client) vs club (server) | Client side 'you' counts all rounds. |
| frontend/src/features/shooters/charts.ts:finishesModel/isFinish (222,215) | scores | CWS | new | place per held Sunday | Relies on percentile non-null. |
| frontend/src/features/shooters/charts.ts:attendanceModel (360), monthsModel (425) | both | CWS | new | calendar best score per day; Sundays per month | Cell colour uses the official best. A * or aria marker is needed, and '★' is already taken by specials. |
| frontend/src/features/shooters/charts.ts:toughDaysModel (453) | scores | XR | new | adjusted vs explorer difficulty | Drops naturally if adjusted is null. |
| frontend/src/features/shooters/components/ProfileHero.tsx (74-118) | scores | MIXED | confirmed | server stats/inWindow avg/median/best, rounds, Sundays | Counts are CWS, averages XR. |
| frontend/src/features/shooters/components/InsightsCard.tsx (51-95) | scores | MIXED | confirmed | server shooter_insights stats | Matches the explainers above. |
| frontend/src/features/yir/pages/YirClubPage.tsx (34,43-55,66-70), YirShooterPage.tsx (34,61,75), yir/charts.ts (14-90) | scores | MIXED | confirmed | server avg, top rounds, perfect, hardest/easiest, best, PBs, monthly avg | Server-computed. |
| frontend/src/features/yir/components/OnThisDayCard.tsx (10-14) | scores | CWS | confirmed | winners and top score | * spot. |
| frontend/src/features/weather/charts.ts:windRoseChart (99) | scores | XR | new | mean of event medians per wind sector (client) | Client-side over WeatherEventOut. Needs an excluded flag or server filtering. |
| frontend/src/features/weather/conditions.ts:summarize (39) | scores | XR | new | mean field median / mean difficulty of matching Sundays (client) | Client-side. |
| frontend/src/features/insights/components/RecapCard.tsx (19), InsightExplainer.tsx (7) | scores | MIXED | confirmed | backend headline / how / how_you | All copy comes from the backend, so disclosure belongs in backend insight 'how'. |
| frontend/src/features/admin-recap/format.ts:formatRecap (50) | scores | CWS | new | recap email text: turnout, rounds, server insights/milestones | Outsider-readable email. Natural place for a one-line 'Station N thrown out; everyone credited' note. Special branch at :55. |
| frontend/src/features/claysmasher/components/ExportScores.tsx (19) | scores | AMBIGUOUS | new | server zip export | Now merged in public. Backend decides the export flag; no UI marker. |
| frontend/src/features/stations/CoverageNote.tsx:CoverageNote (38) | station_hits | XS | new | station Sundays coverage note | A pattern for a muted note on the stations pages. Station stats are all server-computed. |
| frontend/src/lib/csv.ts:toCsv (21) | other | UN | confirmed | generic CSV | CSV columns come from each model. A dropped/excluded column would be added per model. |
| frontend/src/api/schema.d.ts (generated) + features/*/mocks.ts + test/msw/handlers.ts | other | UN | corrected | API types and MSW fixtures | Gitignored and generated by pnpm gen:api. The local copy is STALE (no kind/label/target_total). Fixtures are typed literals, so new required fields mean editing every fixture. |

Open questions:
- Should rounds on a dropped-station Sunday count toward the '5 earlier rounds' PB rule (PbTable isEarly via roundsBefore, pbRoundIds MIN_PB_EARLIER_ROUNDS, and the summary 'personal best counts once there are at least 5 earlier rounds')?
- On the profile trend chart, should excluded rounds still be plotted (with * and no PB pin or line contribution) or left out of the plot entirely?
- Marker glyph: '★' already means a special shoot in the shooter calendar. Is '*' (or another mark) distinct enough, and does the calendar cell need it?
- YIR glance/shooterYear and the odometer define average or hit rate as clays broken ÷ rounds or thrown. With clays broken CWS and average XR, which definition wins in the copy?
- Will the backend null field_median/adjusted on excluded rounds? MePanel.lastResult reads a null field_median as 'partial results'. Should a distinct flag drive the '—' instead?
- Should vs-previous-Sunday skip a dropped Sunday as 'previous', and should a dropped Sunday's own vs_prev deltas show?
- Events difficulty is already about 95 of the 95-word cap. Rewrite it, or put the disclosure in a page-level note instead of the explainer?
- Is a new glossary term ('dropped-station') wanted? It would force terms updates through the explainer lint on every explainer that names it.
- Race explainer is metric-agnostic. Should raceExplainer take the metric so it can disclose XR for avg/best/rating_gain only?
- Should the Explorer min_score filter and the ClaySmasher export include, mark or drop excluded rounds?

## critic

Completeness check of the public repo (the repo @ 79ee0d8). The repo has only 19 commits. dc35e64 "Cleaned for public" is a squashed baseline, so log --stat over it is the whole tree. I compared the 18 later commits (fdff27c through 79ee0d8: bumps/admin analytics, special events #40, ClaySmasher #43/#76, Plan 19 #62, recap #74/#75/#77, copy fixes #78-#81) and every backend/src and frontend/src file that touches scores against the digest. No lane was marked FAILED. The lanes covered the big surfaces well. What is missing is mostly admin/ops plumbing and some frontend chart models, plus one schema blocker.

Structural facts the digest gets wrong or leaves out:

1. SCHEMA BLOCKER: event_metrics.median, mean and top_score are NOT NULL (models/analytics.py:40-43; migrations/versions/0001_initial.py:363-366). Only stdev and difficulty are nullable. Both the analytics lane (point 3) and the insights lane (point 3) suggest that s10 write NULL median/mean/top_score for excluded Sundays so that consumers drop them. Doing that needs migration 0010 to ALTER these columns to nullable. The other way is to skip writing the event_metrics row: the frames LEFT JOIN it (frames.py:156/168, weather_effects.py:68, yir.py:27), so it reads back as NaN. But either way the Sunday's own median and top score vanish from the event page, Latest card and share card, which the frontend lane classes as CWS. So the designer must choose between keeping event_metrics intact and adding the flag to every trend consumer, or a separate 'stats' metrics set. round_metrics field_median, adjusted and residual are already nullable.

2. Frontend admin needs work the API lane said would 'appear automatically'. frontend/src/features/admin-identity/rules.ts:4-24 hard-codes RULE_TYPES and RULE_LABELS as a closed `as const` union, and buildRulePayload (:84) and RuleCreateForm.tsx (:58 round_type_override, :87 station_reset) switch on it. A new drop/undrop rule type therefore needs frontend changes here, plus admin-identity mocks.

3. Duplicated finding-code set. The station preview finding codes appear twice: backend domain/imports.py:64 PREVIEW_STATION_CODES and frontend admin/components/FindingsList.tsx:6 STATION_CODES. A new 'station_dropped' preview finding has to go into both, or it lands in the generic 'other' group. A rebuild-time DataIssue (the precedent at rebuild.py:394) surfaces through api/routes/admin_ops.py:86 data_issues and frontend admin-ops/components/DataIssues.tsx:14/51. That is where admins would see 'Station N looks thrown out on <date>'.

4. Insight Explorer links are built centrally in analytics/insights/charts.py:46 spec() and :71 explorer(), which hold Filters with best_round_only/min_rounds. Every score insight chart passes through here into /api/explore. That makes this the single backend point for an 'exclude stats_excluded' Filters field, if the engine does not apply the exclusion by default. Proof tests (insights/proof.py) compare against these specs.

5. The profile route itself, api/routes/shooters.py:363 get_shooter, is the composer the API lane listed only through its helpers. ShooterDetailOut stats and window_stats mix CWS and XR, odometer is CWS, pbs is XR, and current_mu comes from rating_history (XR). Lifetime and filtered frames both come from one load_rounds, so a single filtered frame changes stats.n_rounds.

6. The shooter Sunday calendar colours each 'shot' cell by that day's best score (components/charts/builders/sundayCalendar.ts:38-72, used by shooters/charts.ts:397 attendanceModel). The frontend lane classed this CWS and attendance. It is a natural place for the * marker, and its tooltip says 'Best score: N'.

7. Club page chart models were not listed. frontend/src/features/club/charts.ts has scoreTrendModel :98 (median/top + rolling8), difficultyModel :124, seasonalityModel :75 (mean_median), distributionModel :156 and firstRoundsModel :309, rendered by ClubCharts.tsx ScoreTrendChart :164, DifficultyChart :189 and DistributionChart :214. Weather has difficultyFitChart :50 and bandScoreChart :142. They are display only, so the server-side exclusion covers them. But a client-side * marker or 'N Sundays left out' note needs a flag in EventTrendOut/WeatherEventOut.

8. Confirmed unaffected, with no new rows needed: jobs/page_warm.py (warms URLs and prunes response_cache by data_version), api/page_cache.py, domain/round_type.py classify (odd target_count, so a dropped station keeps its target_count), domain/diff.py, ingest/scores.py MAX_SCORE, insights/select.py, picks.py, templates.py, types.py (station_sundays readiness), og/html.py and og/render.py (render og/facts output), scripts/* and tools/trophy_art. The only CSV producers are backend ClaySmasher (listed) and frontend lib/csv.ts via ChartCard/ChartFrame (listed as UN). The memory note that 'CSV exports all rows' means chart CSVs carry whatever rows the model has, so a dropped flag column in the CSV is a design choice. There are no other emails besides the recap.

| consumer | uses | cls | status | computes | notes |
|---|---|---|---|---|---|
| backend/src/sunday_clays/models/analytics.py:EventMetric (35) | scores | MIXED | new | event_metrics n/median/mean/stdev/top_score/difficulty; median, mean and top_score are NOT NULL (0001_initial.py:363-366) | Blocks the lanes' 'null median/top_score in s10' idea unless 0010 relaxes NOT NULL. Leaving out the row also hides the day's own (CWS) median/top on the event page, Latest card and share card. |
| backend/src/sunday_clays/analytics/steps/s10_metrics.py:_INSERT_EVENT_METRICS (17) | scores | MIXED | corrected | INSERT of every computed event_metrics row; s30_skill.py:22 _UPDATE_EVENTS sets difficulty | Hook point for any event-level nulling. Only difficulty (s30) and stdev can take NULL without a migration. |
| backend/src/sunday_clays/analytics/insights/charts.py:spec/explorer (46/71) | scores | MIXED | new | Builds the Explorer QuerySpec (Filters date window, shooter_ids, min_rounds, best_round_only) for every insight chart link | Central backend point to add an exclusion Filters field for XR-metric insight charts. Must agree with explorer/engine and insights/proof.py. |
| backend/src/sunday_clays/api/routes/shooters.py:get_shooter (363) | scores | MIXED | new | Profile detail: stats and window_stats via shooter_stats over load_rounds, odometer (lifetime), pbs via personal_bests, current_mu from rating_history, streaks via appearances | API lane listed only the helpers. n_rounds/odometer are CWS; avg/best/pbs/current_mu are XR; one frame feeds both. |
| backend/src/sunday_clays/api/routes/admin_ops.py:data_issues (86) | other | UN | new | Lists data_issues rows by code for admins | Surface for a rebuild-time 'station dropped' DataIssue (precedent rebuild.py:394). No code change unless copy is wanted. |
| frontend/src/features/admin-ops/components/DataIssues.tsx:groupIssues/DataIssues (14/58) | other | UN | new | Groups data issues by code; code-specific action at :51 (station_name_unmatched) | A new dropped-station issue code shows up generically. Optionally add a code-specific action, such as a 'not a drop' override. |
| frontend/src/features/admin/components/FindingsList.tsx:STATION_CODES/groupFindings (6/16) | station_hits | UN | new | Import-preview 'Station vs score' group; a hard-coded copy of backend PREVIEW_STATION_CODES | A new preview finding code must be added here as well as to domain/imports.py:64, or it falls into the 'other' group. |
| frontend/src/features/admin-identity/rules.ts:RULE_TYPES/RULE_LABELS/buildRulePayload (4/15/84) | other | UN | new | Closed union of the 8 rule types, their labels and payload builders | Corrects the API lane's claim that a new RuleType 'appears automatically'. The backend accepts it, but the admin UI needs a new entry, label, fields and payload case. |
| frontend/src/features/admin-identity/components/RuleCreateForm.tsx:RuleCreateForm (121; fields switch 58/87) | other | UN | new | Per-rule-type form fields (round_type_override event date, station_reset station label) | A drop/undrop rule needs fields for event_date and station label (reuse stationLabel rules.ts:76 for 7A labels). |
| frontend/src/components/charts/builders/sundayCalendar.ts:sundayCalendarOption (47) | scores | CWS | new | Shooter Sunday calendar; shot cells coloured by best score that day, tooltip 'Best score: N' (:72); special cell state | Used by shooters/charts.ts:397. The official score is shown, so this is a candidate * spot. Watch the existing star meaning 'special'. |
| frontend/src/features/club/charts.ts:scoreTrendModel/difficultyModel (98/124) | scores | XR | new | Per-Sunday median/top score + rolling-8 averages; per-Sunday difficulty | Renders EventTrendOut from club_insights.event_trends. The server must drop or flag excluded Sundays, and the rolling8 is computed server side. |
| frontend/src/features/club/charts.ts:seasonalityModel/distributionModel/firstRoundsModel (75/156/309) | scores | XR | new | Monthly mean median; score distribution per year; first-round scores | Display of server data from club_insights.seasonality, club_distribution and cohorts.first_round_scores. Rendered by ClubCharts.tsx SeasonalityChart :139, ScoreTrendChart :164, DifficultyChart :189, DistributionChart :214. |
| frontend/src/features/weather/charts.ts:difficultyFitChart/bandScoreChart (50/142) | scores | XR | new | Difficulty vs weather scatter/fit; mean score per weather band | Frontend lane listed only windRoseChart. Both chart weather_events/effects data that the server must exclude. |
| frontend/src/features/shooters/components/OdometerStrip.tsx (11-14) | scores | CWS | new | Clays broken and hit rate = broken/thrown | Component that renders the odometer explainer (listed). Clays broken counts the official score, credited station included. |
| frontend/src/features/stations/StationBreakdown.tsx / pages/StationsPage.tsx (20-116 / 42-102) | station_hits | XS | new | Station hit % tables and per-Sunday station hit % series (e.hit_pct per event_date and label) | Display only. The dropped station's per-Sunday rows must vanish server side (StationEventPctOut). The CSV columns come from these tables. |
| frontend/src/features/events/components/StationHeatmap.tsx (25) | station_hits | XS | new | Sunday station-hits heatmap and CSV from stationMatrixModel | Renderer for events/charts.ts stationMatrixModel (listed). Needs StationLayoutOut.dropped to mark the column. |

Open questions:
- event_metrics NOT NULL: relax median/mean/top_score in 0010, or keep event_metrics whole for the day (CWS on the Sunday page) and filter every trend/club/yir/weather consumer on a stats_excluded flag instead?
- Should a dropped-station Sunday's insight Explorer charts get the exclusion through a new Filters field set in insights/charts.py spec(), or through an engine default for XR metrics? The proof tests must agree with whichever is chosen.
- Admin override: one rule type with a force on/off payload, or two (dropped/not_dropped)? Either way frontend admin-identity/rules.ts and RuleCreateForm.tsx need new cases.

