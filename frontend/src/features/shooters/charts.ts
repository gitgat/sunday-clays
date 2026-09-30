import type { EChartsOption } from 'echarts';
import { barOption } from '../../components/charts/builders/bar';
import { lineOption } from '../../components/charts/builders/line';
import { scatterOption } from '../../components/charts/builders/scatter';
import { sundayCalendarOption } from '../../components/charts/builders/sundayCalendar';
import type { TabularData, TabularRow } from '../../components/charts/types';
import type {
  ClubDistributionGroup,
  RatingPoint,
  ShooterInsights,
  ShooterRound,
  SplitRow,
} from './api';
import { MIN_CLUB_SHOOTERS, MIN_PB_EARLIER_ROUNDS } from './format';

export type ChartModel = TabularData & { option: EChartsOption };

const round1 = (v: number) => Math.round(v * 10) / 10;

/** Rating on the published scale with the server's ±1.96·√var likely range `lo..hi` (C7) and a pin on the peak (Decision D12). */
export function ratingModel(points: RatingPoint[]) {
  const rows = points.map((p) => ({
    event_date: p.event_date,
    rating: round1(p.mu),
    low: round1(p.lo),
    high: round1(p.hi),
  }));
  let peak: (typeof rows)[number] | null = null;
  for (const r of rows) if (peak === null || r.rating > peak.rating) peak = r;
  const option: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Rating', 'Likely range'] },
    xAxis: { type: 'category', boundaryGap: false, data: rows.map((r) => r.event_date) },
    yAxis: { type: 'value', scale: true, name: 'Rating' },
    series: [
      {
        name: 'band-low',
        type: 'line',
        stack: 'band',
        symbol: 'none',
        lineStyle: { opacity: 0 },
        silent: true,
        data: rows.map((r) => r.low),
      },
      {
        name: 'Likely range',
        type: 'line',
        stack: 'band',
        symbol: 'none',
        lineStyle: { opacity: 0 },
        areaStyle: { opacity: 0.25 },
        data: rows.map((r) => round1(r.high - r.low)),
      },
      {
        name: 'Rating',
        type: 'line',
        symbol: 'none',
        data: rows.map((r) => r.rating),
        markPoint:
          peak === null
            ? undefined
            : {
                data: [{ name: 'Peak', coord: [peak.event_date, peak.rating], value: peak.rating }],
              },
      },
    ],
  };
  return {
    columns: [
      { key: 'event_date', label: 'Date', type: 'date' },
      { key: 'rating', label: 'Rating', type: 'number' },
      { key: 'low', label: 'Likely low', type: 'number' },
      { key: 'high', label: 'Likely high', type: 'number' },
    ] satisfies TabularData['columns'],
    rows,
    option,
  };
}

/** C12 personal_bests rule (Decision D10): at most one PB per date, the lowest-ordinal top round. */
export function pbRoundIds(rounds: ShooterRound[]): Set<number> {
  const byDate = new Map<string, ShooterRound[]>();
  for (const r of rounds) byDate.set(r.event_date, [...(byDate.get(r.event_date) ?? []), r]);
  const pbs = new Set<number>();
  let best = -Infinity;
  let earlier = 0;
  for (const date of [...byDate.keys()].sort()) {
    const day = byDate.get(date) as ShooterRound[];
    const top = day.reduce((a, b) =>
      b.score > a.score || (b.score === a.score && b.ordinal < a.ordinal) ? b : a,
    );
    if (earlier >= MIN_PB_EARLIER_ROUNDS && top.score > best) pbs.add(top.round_id);
    best = Math.max(best, top.score);
    earlier += day.length;
  }
  return pbs;
}

/** Lines an insight can switch on over the scores (Plan 12): all worked out per Sunday shot. */
export const TREND_LINES = ['roll10', 'roll20', 'so_far', 'pb'] as const;
export type TrendLine = (typeof TREND_LINES)[number];
export const TREND_LINE_LABELS: Record<TrendLine, string> = {
  roll10: '10-Sunday average',
  roll20: '20-Sunday average',
  so_far: 'Average so far',
  pb: 'Personal best',
};

function mean(values: readonly number[]): number {
  return values.reduce((a, b) => a + b, 0) / values.length;
}

/**
 * The line's value on each date (the insight engine's rule, spec §3.6): best round per Sunday for
 * the rolling averages and the personal best; every round before that date for "so far".
 */
export function trendLineByDate(
  rounds: ShooterRound[],
  line: TrendLine,
): Map<string, number | null> {
  const dates = [...new Set(rounds.map((r) => r.event_date))].sort();
  const bests: number[] = [];
  const before: number[] = [];
  const out = new Map<string, number | null>();
  for (const date of dates) {
    const day = rounds.filter((r) => r.event_date === date).map((r) => r.score);
    const soFar = before.length > 0 ? round1(mean(before)) : null;
    bests.push(Math.max(...day));
    const window = line === 'roll10' ? 10 : line === 'roll20' ? 20 : 0;
    if (line === 'so_far') out.set(date, soFar);
    else if (line === 'pb') out.set(date, Math.max(...bests));
    else out.set(date, bests.length >= window ? round1(mean(bests.slice(-window))) : null);
    before.push(...day);
  }
  return out;
}

/**
 * Score (left axis, 0–50) and score vs the day's middle score (right axis) per round, PB pins on
 * the score line, and optionally one insight line (Plan 12) on the score axis.
 */
export function trendModel(rounds: ShooterRound[], line: TrendLine | null = null) {
  const sorted = [...rounds].sort(
    (a, b) => a.event_date.localeCompare(b.event_date) || a.ordinal - b.ordinal,
  );
  const pbs = pbRoundIds(sorted);
  const lineByDate = line === null ? null : trendLineByDate(sorted, line);
  const rows = sorted.map((r) => ({
    event_date: r.event_date,
    score: r.score,
    adjusted: r.adjusted,
    pb: pbs.has(r.round_id) ? 'PB' : '',
    ...(lineByDate === null ? {} : { line: lineByDate.get(r.event_date) ?? null }),
  }));
  const lineName = line === null ? null : TREND_LINE_LABELS[line];
  const option: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Score', 'Vs middle score', ...(lineName === null ? [] : [lineName])] },
    xAxis: { type: 'category', data: rows.map((r) => r.event_date) },
    yAxis: [
      { type: 'value', name: 'Score', min: 0, max: 50 },
      { type: 'value', name: 'Vs middle score' },
    ],
    series: [
      {
        name: 'Score',
        type: 'line',
        symbolSize: 4,
        data: rows.map((r) => r.score),
        markPoint: {
          symbol: 'pin',
          data: rows.flatMap((r, i) =>
            r.pb ? [{ name: 'PB', coord: [i, r.score], value: r.score }] : [],
          ),
        },
      },
      {
        name: 'Vs middle score',
        type: 'line',
        yAxisIndex: 1,
        symbolSize: 4,
        data: rows.map((r) => r.adjusted),
      },
      ...(lineName === null
        ? []
        : [
            {
              name: lineName,
              type: 'line' as const,
              step: line === 'pb' ? ('end' as const) : undefined,
              showSymbol: false,
              lineStyle: { width: 3 },
              data: rows.map((r) => lineByDate?.get(r.event_date) ?? null),
            },
          ]),
    ],
  };
  return {
    columns: [
      { key: 'event_date', label: 'Date', type: 'date' },
      { key: 'score', label: 'Score', type: 'int' },
      { key: 'adjusted', label: 'Vs middle score', type: 'number' },
      { key: 'pb', label: 'PB', type: 'string' },
      ...(lineName === null ? [] : [{ key: 'line', label: lineName, type: 'number' as const }]),
    ] satisfies TabularData['columns'],
    rows,
    option,
  };
}

/**
 * A best round on a Sunday with full results. `event_rank` is set even on Sundays with partial
 * results, but `percentile` is null exactly when the Sunday is not held (or the round is not the best).
 */
export const isFinish = (r: ShooterRound): boolean =>
  r.is_best_round && r.event_rank !== null && r.percentile !== null;

/**
 * Finish on every Sunday with full results (best round's place, ties sharing it), 1st at the top
 * (Plan 12 `finishes`, the podium-run and first-since charts).
 */
export function finishesModel(rounds: ShooterRound[]): ChartModel {
  const rows = [...rounds]
    .filter(isFinish)
    .sort((a, b) => a.event_date.localeCompare(b.event_date))
    .map((r) => ({ event_date: r.event_date, place: r.event_rank }));
  const columns: TabularData['columns'] = [
    { key: 'event_date', label: 'Sunday', type: 'date' },
    { key: 'place', label: 'Place', type: 'int' },
  ];
  const option: EChartsOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: rows.map((r) => r.event_date) },
    yAxis: { type: 'value', name: 'Place', inverse: true, min: 1, minInterval: 1 },
    series: [
      {
        name: 'Place',
        type: 'line',
        symbolSize: 8,
        lineStyle: { opacity: 0.35 },
        data: rows.map((r) => r.place),
        markLine: {
          symbol: 'none',
          silent: true,
          data: [{ yAxis: 3, name: 'Podium' }],
          label: { formatter: 'Podium' },
          lineStyle: { type: 'dashed' },
        },
      },
    ],
  };
  return { columns, rows, option };
}

/** Left-aligns the legend and stops it short of the ChartFrame zoom toolbox at the top right (phones). */
function clearOfToolbox(option: EChartsOption): EChartsOption {
  return { ...option, legend: { ...(option.legend as object), left: 0, right: 110 } };
}

function share(count: number, total: number): number {
  return total === 0 ? 0 : round1((100 * count) / total);
}

/** The shooter's score shares vs the club's all-years shares (Decision D11). */
export function distributionModel(
  rounds: ShooterRound[],
  groups: ClubDistributionGroup[],
): ChartModel {
  const you = new Map<number, number>();
  for (const r of rounds) you.set(r.score, (you.get(r.score) ?? 0) + 1);
  const club = new Map<number, number>();
  for (const g of groups)
    g.counts.forEach((n, score) => club.set(score, (club.get(score) ?? 0) + n));
  const clubTotal = [...club.values()].reduce((a, b) => a + b, 0);
  const seen = [...you.keys(), ...[...club.entries()].filter(([, n]) => n > 0).map(([s]) => s)];
  const columns: TabularData['columns'] = [
    { key: 'score', label: 'Score', type: 'int' },
    { key: 'you_pct', label: 'You %', type: 'number' },
    { key: 'club_pct', label: 'Club %', type: 'number' },
  ];
  const lo = seen.length === 0 ? 51 : Math.min(...seen);
  const rows = Array.from({ length: 51 - lo }, (_, i) => {
    const score = lo + i;
    return {
      score,
      you_pct: share(you.get(score) ?? 0, rounds.length),
      club_pct: share(club.get(score) ?? 0, clubTotal),
    };
  });
  return {
    columns,
    rows,
    option: clearOfToolbox(
      barOption(
        { columns, rows },
        { x: 'score', y: ['you_pct', 'club_pct'], yName: 'Share of rounds (%)' },
      ),
    ),
  };
}

export function learningCurveModel(
  curve: ShooterInsights['learning_curve'],
): ChartModel & { clubHidden: boolean } {
  const columns: TabularData['columns'] = [
    { key: 'k', label: 'Your Sunday #', type: 'int' },
    { key: 'you', label: 'You (vs middle score)', type: 'number' },
    { key: 'club', label: 'Club middle', type: 'number' },
    { key: 'club_n', label: 'Club shooters', type: 'int' },
  ];
  // A club point backed by fewer than 3 shooters is one person's luck: shown as a gap ("—" in the table).
  const rows = curve.map((p) => ({
    k: p.k,
    you: p.value,
    club: p.n_club >= MIN_CLUB_SHOOTERS ? p.club_median : null,
    club_n: p.n_club,
  }));
  const clubHidden = curve.some((p) => p.club_median !== null && p.n_club < MIN_CLUB_SHOOTERS);
  return {
    columns,
    rows,
    clubHidden,
    option: clearOfToolbox(
      lineOption({ columns, rows }, { x: 'k', y: ['you', 'club'], yName: 'Vs middle score' }),
    ),
  };
}

export function splitsModel(splits: SplitRow[]): ChartModel {
  const columns: TabularData['columns'] = [
    { key: 'key', label: 'Group', type: 'string' },
    { key: 'n_rounds', label: 'Rounds', type: 'int' },
    { key: 'avg', label: 'Average', type: 'number' },
    { key: 'median', label: 'Median', type: 'number' },
    { key: 'best', label: 'Best', type: 'int' },
  ];
  const rows = splits.map((s) => ({
    key: s.key,
    n_rounds: s.n_rounds,
    avg: round1(s.avg),
    median: s.median,
    best: s.best,
  }));
  return { columns, rows, option: barOption({ columns, rows }, { x: 'key', y: ['avg'] }) };
}

export function activeYears(rounds: ShooterRound[]): number[] {
  return [...new Set(rounds.map((r) => Number(r.event_date.slice(0, 4))))].sort((a, b) => b - a);
}

/**
 * One row per Sunday of `year` that has a cell: 'shot' with the best score of the shooter's rounds
 * that day, or 'missed' for any club-held Sunday (`heldDates`) of that year they did not shoot.
 */
export function attendanceModel(
  rounds: ShooterRound[],
  heldDates: readonly string[],
  year: number,
): ChartModel {
  const best = new Map<string, number>();
  for (const r of rounds) {
    if (!r.event_date.startsWith(`${year}-`)) continue;
    best.set(r.event_date, Math.max(best.get(r.event_date) ?? 0, r.score));
  }
  const columns: TabularData['columns'] = [
    { key: 'date', label: 'Sunday', type: 'date' },
    { key: 'state', label: 'State', type: 'string' },
    { key: 'score', label: 'Best score', type: 'int' },
  ];
  const rows: TabularData['rows'] = [...best.entries()].map(([date, score]) => ({
    date,
    state: 'shot',
    score,
  }));
  for (const date of heldDates) {
    if (date.startsWith(`${year}-`) && !best.has(date)) {
      rows.push({ date, state: 'missed', score: null });
    }
  }
  rows.sort((a, b) => String(a.date).localeCompare(String(b.date)));
  return {
    columns,
    rows,
    option: sundayCalendarOption(
      { columns, rows },
      { date: 'date', value: 'score', state: 'state', year },
    ),
  };
}

/** Rounds on days before `date`: a best needs 5 of them to count as a personal best (the trophy rule). */
export function roundsBefore(rounds: readonly ShooterRound[], date: string): number {
  return rounds.filter((r) => r.event_date < date).length;
}

/** `YYYY-MM` of every month from `first` to `last` (both `YYYY-MM`), in order. */
export function monthsBetween(first: string, last: string): string[] {
  const out: string[] = [];
  let [y, m] = first.split('-').map(Number) as [number, number];
  for (;;) {
    const key = `${String(y)}-${String(m).padStart(2, '0')}`;
    if (key > last) return out;
    out.push(key);
    [y, m] = m === 12 ? [y + 1, 1] : [y, m + 1];
  }
}

/**
 * The calendar's month view (Plan 12 `cal.view=month`): Sundays shot in each month from the first
 * month to the last, empty months included. Categories are `YYYY-MM`, the keys insights highlight.
 */
export function monthsModel(rounds: ShooterRound[]): ChartModel {
  const columns: TabularData['columns'] = [
    { key: 'month', label: 'Month', type: 'string' },
    { key: 'sundays', label: 'Sundays shot', type: 'int' },
  ];
  const dates = [...new Set(rounds.map((r) => r.event_date))].sort();
  const counts = new Map<string, number>();
  for (const d of dates) counts.set(d.slice(0, 7), (counts.get(d.slice(0, 7)) ?? 0) + 1);
  const first = dates[0];
  const last = dates[dates.length - 1];
  const rows =
    first === undefined || last === undefined
      ? []
      : monthsBetween(first.slice(0, 7), last.slice(0, 7)).map((month) => ({
          month,
          sundays: counts.get(month) ?? 0,
        }));
  return { columns, rows, option: barOption({ columns, rows }, { x: 'month', y: ['sundays'] }) };
}

/**
 * Plan 12 `tough-days`: each Sunday's best round against the field (y) by how the day played (x,
 * the Explorer's `difficulty` per event; positive = harder). Points are named by date, so an
 * insight's date highlights ring them. Sundays without either number are left out.
 */
export function toughDaysModel(
  rounds: ShooterRound[],
  difficulty: readonly TabularRow[],
): ChartModel {
  const byDate = new Map<string, number>();
  for (const row of difficulty) {
    if (typeof row.event === 'string' && typeof row.value === 'number') {
      byDate.set(row.event.slice(0, 10), row.value);
    }
  }
  const columns: TabularData['columns'] = [
    { key: 'event_date', label: 'Sunday', type: 'date' },
    { key: 'difficulty', label: 'How the day played', type: 'number' },
    { key: 'adjusted', label: 'Against the field', type: 'number' },
  ];
  const rows = rounds.flatMap((r) => {
    const played = byDate.get(r.event_date);
    if (!r.is_best_round || r.adjusted === null || played === undefined) return [];
    return [{ event_date: r.event_date, difficulty: round1(played), adjusted: round1(r.adjusted) }];
  });
  rows.sort((a, b) => a.event_date.localeCompare(b.event_date));
  return {
    columns,
    rows,
    option: scatterOption(
      { columns, rows },
      {
        x: 'difficulty',
        y: 'adjusted',
        label: 'event_date',
        xName: 'How the day played (+ = harder)',
        yName: 'Against the field',
      },
    ),
  };
}
