import type { EChartsOption } from 'echarts';
import { barOption } from '../../components/charts/builders/bar';
import { lineOption } from '../../components/charts/builders/line';
import { ridgelineOption } from '../../components/charts/builders/ridgeline';
import type { TabularData } from '../../components/charts/types';
import type {
  AttendancePoint,
  Cohort,
  ConversionYear,
  DistributionGroup,
  FirstRounds,
  EventTrend,
  MonthTrend,
  ParityYear,
  StatusYear,
  YearTrend,
} from './api';
import { monthShort, pct1, round1 } from './format';

export type ChartModel = TabularData & { option: EChartsOption };

type Column = TabularData['columns'][number];
const col = (key: string, label: string, type: Column['type']): Column => ({ key, label, type });
const r1 = (v: number | null) => (v === null ? null : round1(v));

const byDate = <T extends { event_date: string }>(rows: T[]) =>
  [...rows].sort((a, b) => a.event_date.localeCompare(b.event_date));
const byYear = <T extends { year: number }>(rows: T[]) => [...rows].sort((a, b) => a.year - b.year);

/** Head count against rounds scored (more rounds than shooters on doubleheader days). */
export function attendanceModel(points: AttendancePoint[]): ChartModel {
  const columns = [
    col('event_date', 'Date', 'date'),
    col('head_count', 'Head count', 'int'),
    col('rounds', 'Rounds scored', 'int'),
    col('shooters', 'Shooters with scores', 'int'),
  ];
  const rows = byDate(points).map((p) => ({
    event_date: p.event_date,
    head_count: p.head_count,
    rounds: p.n_rounds,
    shooters: p.n_shooters,
  }));
  return {
    columns,
    rows,
    option: lineOption({ columns, rows }, { x: 'event_date', y: ['head_count', 'rounds'] }),
  };
}

export function yearTrendsModel(years: YearTrend[]): ChartModel {
  const columns = [
    col('year', 'Year', 'string'),
    col('events_held', 'Sundays with full results', 'int'),
    col('mean_head_count', 'Mean head count', 'number'),
    col('unique_shooters', 'Unique shooters', 'int'),
    col('ytd_events', 'Sundays so far this year', 'int'),
    col('ytd_events_yoy_pct', 'Year-to-date change %', 'number'),
  ];
  const rows = byYear(years).map((y) => ({
    year: String(y.year),
    events_held: y.events_held,
    mean_head_count: r1(y.mean_head_count),
    unique_shooters: y.unique_shooters,
    ytd_events: y.ytd_events,
    ytd_events_yoy_pct: pct1(y.ytd_events_yoy),
  }));
  return {
    columns,
    rows,
    option: barOption({ columns, rows }, { x: 'year', y: ['unique_shooters', 'events_held'] }),
  };
}

export function seasonalityModel(months: MonthTrend[]): ChartModel {
  const columns = [
    col('month', 'Month', 'string'),
    col('n_events', 'Sundays', 'int'),
    col('mean_head_count', 'Mean head count', 'number'),
    col('mean_median', 'Average middle score', 'number'),
  ];
  const rows = [...months]
    .sort((a, b) => a.month - b.month)
    .map((m) => ({
      month: monthShort(m.month),
      n_events: m.n_events,
      mean_head_count: r1(m.mean_head_count),
      mean_median: r1(m.mean_median),
    }));
  return {
    columns,
    rows,
    option: barOption({ columns, rows }, { x: 'month', y: ['mean_head_count'] }),
  };
}

/** Middle and top score per Sunday with full results, with the server's 8-Sunday averages (Plan 06 T9). */
export function scoreTrendModel(events: EventTrend[]): ChartModel {
  const columns = [
    col('event_date', 'Date', 'date'),
    col('median', 'Middle score', 'number'),
    col('median_rolling8', 'Middle score (8-Sunday average)', 'number'),
    col('top_score', 'Top score', 'int'),
    col('top_score_rolling8', 'Top score (8-Sunday average)', 'number'),
  ];
  const rows = byDate(events).map((e) => ({
    event_date: e.event_date,
    median: e.median,
    median_rolling8: round1(e.median_rolling8),
    top_score: e.top_score,
    top_score_rolling8: round1(e.top_score_rolling8),
  }));
  return {
    columns,
    rows,
    option: lineOption(
      { columns, rows },
      { x: 'event_date', y: ['median', 'median_rolling8', 'top_score', 'top_score_rolling8'] },
    ),
  };
}

/** Published difficulty (positive = harder than a typical recent day, C7) with the server's rolling mean. */
export function difficultyModel(events: EventTrend[]): ChartModel {
  const columns = [
    col('event_date', 'Date', 'date'),
    col('difficulty', 'Difficulty', 'number'),
    col('difficulty_rolling8', 'Difficulty (8-Sunday average)', 'number'),
  ];
  const rows = byDate(events).map((e) => ({
    event_date: e.event_date,
    difficulty: r1(e.difficulty),
    difficulty_rolling8: r1(e.difficulty_rolling8),
  }));
  return {
    columns,
    rows,
    option: lineOption(
      { columns, rows },
      { x: 'event_date', y: ['difficulty', 'difficulty_rolling8'] },
    ),
  };
}

/** One (year, score) row per round — the ridgeline builder's input — newest year first, so it is the top ridge. */
export function distributionObservations(groups: DistributionGroup[]): TabularData {
  const newestFirst = [...groups].sort((a, b) => b.key.localeCompare(a.key));
  return {
    columns: [col('year', 'Year', 'string'), col('score', 'Score', 'int')],
    rows: newestFirst.flatMap((g) =>
      g.counts.flatMap((n, score) => Array.from({ length: n }, () => ({ year: g.key, score }))),
    ),
  };
}

export function distributionModel(groups: DistributionGroup[]): ChartModel {
  const columns = [
    col('year', 'Year', 'string'),
    col('n', 'Rounds', 'int'),
    col('mean', 'Average', 'number'),
    col('p10', 'Low end', 'number'),
    col('p25', 'Lower middle', 'number'),
    col('median', 'Middle score', 'number'),
    col('p75', 'Upper middle', 'number'),
    col('p90', 'High end', 'number'),
  ];
  const rows = [...groups]
    .sort((a, b) => a.key.localeCompare(b.key))
    .map((g) => ({
      year: g.key,
      n: g.n,
      mean: round1(g.mean),
      p10: g.p10,
      p25: g.p25,
      median: g.median,
      p75: g.p75,
      p90: g.p90,
    }));
  return {
    columns,
    rows,
    option: ridgelineOption(distributionObservations(groups), { group: 'year', value: 'score' }),
  };
}

const cohortColumns = [
  col('year', 'Year', 'string'),
  col('n_new', 'Newcomers', 'int'),
  col('n_returned', 'Came back', 'int'),
  col('retained_1y_pct', 'Shot again next year %', 'number'),
  col('retained_2y_pct', 'Shot again year after %', 'number'),
];

/** Share of a cohort still shooting `offset` calendar years later; null until that year has data. */
function retentionPct(c: Cohort, offset: number): number | null {
  return pct1(c.retention.find((r) => r.offset === offset)?.share ?? null);
}

function cohortRows(cohorts: Cohort[]) {
  return byYear(cohorts).map((c) => ({
    year: String(c.year),
    n_new: c.n_new,
    n_returned: c.n_returned,
    retained_1y_pct: retentionPct(c, 1),
    retained_2y_pct: retentionPct(c, 2),
  }));
}

export function newcomersModel(cohorts: Cohort[]): ChartModel {
  const rows = cohortRows(cohorts);
  return {
    columns: cohortColumns,
    rows,
    option: barOption({ columns: cohortColumns, rows }, { x: 'year', y: ['n_new', 'n_returned'] }),
  };
}

export function retentionModel(cohorts: Cohort[]): ChartModel {
  const rows = cohortRows(cohorts);
  return {
    columns: cohortColumns,
    rows,
    option: lineOption(
      { columns: cohortColumns, rows },
      { x: 'year', y: ['retained_1y_pct', 'retained_2y_pct'] },
    ),
  };
}

/** Rounds per year by the status recorded on each round (C7), stacked. */
export function memberGuestModel(statusByYear: StatusYear[]): ChartModel {
  const columns = [
    col('year', 'Year', 'string'),
    col('member_rounds', 'Member rounds', 'int'),
    col('guest_rounds', 'Guest rounds', 'int'),
    col('deceased_rounds', 'In memoriam rounds', 'int'),
    col('unrecorded_rounds', 'Status not recorded', 'int'),
  ];
  const rows = byYear(statusByYear).map((y) => ({
    year: String(y.year),
    member_rounds: y.member_rounds,
    guest_rounds: y.guest_rounds,
    deceased_rounds: y.deceased_rounds,
    unrecorded_rounds: y.unrecorded_rounds,
  }));
  return {
    columns,
    rows,
    option: barOption(
      { columns, rows },
      {
        x: 'year',
        y: ['member_rounds', 'guest_rounds', 'deceased_rounds', 'unrecorded_rounds'],
        stack: true,
      },
    ),
  };
}

/** Rate = guests first seen that year who later joined / new guests that year (never above 100%). */
export function conversionModel(years: ConversionYear[]): ChartModel {
  const columns = [
    col('year', 'Year', 'string'),
    col('new_guests', 'First-time guests', 'int'),
    col('converted', 'Later joined as members', 'int'),
    col('rate_pct', 'Joined %', 'number'),
    col('median_days', 'Median days to join', 'number'),
  ];
  const rows = byYear(years).map((y) => ({
    year: String(y.year),
    new_guests: y.new_guests,
    converted: y.converted,
    rate_pct: y.new_guests === 0 ? null : pct1(y.converted / y.new_guests),
    median_days: y.median_days_to_convert,
  }));
  return {
    columns,
    rows,
    option: barOption({ columns, rows }, { x: 'year', y: ['new_guests', 'converted'] }),
  };
}

export function parityModel(years: ParityYear[]): ChartModel {
  const columns = [
    col('year', 'Year', 'string'),
    col('n_events', 'Sundays', 'int'),
    col('distinct_winners', 'Different winners', 'int'),
    col('top3_share_pct', 'Top-3 share of wins %', 'number'),
    col('favorite_win_pct', 'Favorite’s win rate %', 'number'),
  ];
  const rows = byYear(years).map((y) => ({
    year: String(y.year),
    n_events: y.n_events,
    distinct_winners: y.distinct_winners,
    top3_share_pct: pct1(y.top3_share),
    favorite_win_pct: pct1(y.favorite_win_rate),
  }));
  return {
    columns,
    rows,
    option: lineOption({ columns, rows }, { x: 'year', y: ['top3_share_pct', 'favorite_win_pct'] }),
  };
}

/**
 * First rounds per score (Plan 12 `first-rounds`), from the lowest to the highest score anyone
 * opened with. Categories are the scores as text, so an insight's `hl=38` rings the 38 bar.
 */
export function firstRoundsModel(data: FirstRounds): ChartModel {
  const columns = [
    col('score', 'First-round score', 'string'),
    col('n', 'Shooters', 'int'),
    col('share_pct', 'Share of first rounds (%)', 'number'),
  ];
  const used = data.counts.flatMap((n, score) => (n > 0 ? [score] : []));
  const low = used[0] ?? 0;
  const high = used[used.length - 1] ?? -1;
  const rows = data.counts.slice(low, high + 1).map((n, i) => ({
    score: String(low + i),
    n,
    share_pct: data.n === 0 ? 0 : round1((100 * n) / data.n),
  }));
  return { columns, rows, option: barOption({ columns, rows }, { x: 'score', y: ['n'] }) };
}
