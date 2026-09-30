import { keepPreviousData, useQuery } from '@tanstack/react-query';
import type { EChartsOption, LineSeriesOption } from 'echarts';
import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import { barOption } from './builders/bar';
import { cellLabel, distinct, numeric } from './builders/common';
import { heatmapOption } from './builders/heatmap';
import { lineOption } from './builders/line';
import type { ChartType, TabularData, TabularRow } from './types';

export type QuerySpec = components['schemas']['QuerySpec'];
export type QueryResult = components['schemas']['QueryResult'];
export type Filters = components['schemas']['Filters'];
export type Metric = components['schemas']['Metric'];
export type Dim = components['schemas']['Dim'];
export type Agg = components['schemas']['Agg'];

export const METRIC_LABELS: Record<Metric, string> = {
  score: 'Score',
  adjusted: 'Adjusted score',
  residual: 'Vs expected',
  rating: 'Rating',
  rounds: 'Rounds',
  shooters: 'Shooters',
  attendance: 'Attendance',
  wins: 'Wins',
  hit_pct: 'Hit %',
  difficulty: 'How the day played',
};

export const DIM_LABELS: Record<Dim, string> = {
  shooter: 'Shooter',
  event: 'Sunday',
  month: 'Month',
  year: 'Year',
  season: 'Time of year',
  month_of_year: 'Month of year',
  round_type: 'Round type',
  gauge: 'Gauge',
  status: 'Status',
  temp_band: 'Temperature',
  wind_band: 'Wind',
  precip_band: 'Precipitation',
  condition: 'Conditions',
  station: 'Station',
};

export const AGG_LABELS: Record<Agg, string> = {
  avg: 'Average',
  median: 'Median',
  max: 'Max',
  min: 'Min',
  sum: 'Total',
  count: 'Count',
  p90: '90th percentile',
  stdev: 'Std dev',
  p25: 'Low end (25th percentile)',
};

export const METRICS = Object.keys(METRIC_LABELS) as Metric[];
export const DIMS = Object.keys(DIM_LABELS) as Dim[];
export const AGGS = Object.keys(AGG_LABELS) as Agg[];

/**
 * Metrics that are one value per Sunday, not per round (the backend's EVENT_METRICS): the engine
 * rejects shooter-level filters for them (400 invalid_query) and reports no round count.
 */
export const EVENT_METRICS: ReadonlySet<Metric> = new Set<Metric>(['attendance', 'difficulty']);

/** Whether the best-round-only filter applies to a metric (not to a Sunday total). */
export function bestRoundApplies(metric: Metric): boolean {
  return !EVENT_METRICS.has(metric);
}

export const DEFAULT_FILTERS: Filters = {
  best_round_only: false,
  gauges: [],
  min_rounds: 0,
  round_types: [],
  shooter_ids: [],
  statuses: [],
};

export type QuerySpecInput = Pick<QuerySpec, 'metric'> &
  Partial<Omit<QuerySpec, 'metric' | 'filters'>> & { filters?: Partial<Filters> };

/** A complete QuerySpec from the fields a caller cares about (server defaults for the rest). */
export function querySpec(input: QuerySpecInput): QuerySpec {
  return {
    agg: 'avg',
    group_by: [],
    sort: 'key_asc',
    limit: 500,
    ...input,
    filters: { ...DEFAULT_FILTERS, ...input.filters },
  };
}

/** The most rows one query returns: backend `explorer/spec.py` `limit: Field(default=500, le=5000)`. */
export const EXPLORE_MAX_LIMIT = 5000;

/** The same query asking for every row the engine allows (fullscreen and CSV). */
export function allRowsSpec(spec: QuerySpec): QuerySpec {
  return { ...spec, limit: EXPLORE_MAX_LIMIT };
}

/** allRowsSpec with no From/To dates: the whole history, whatever window the card shows. */
export function allHistorySpec(spec: QuerySpec): QuerySpec {
  const all = allRowsSpec(spec);
  return { ...all, filters: { ...all.filters, date_from: null, date_to: null } };
}

export interface ExploreData {
  /** The spec that produced `result` (while a new spec loads, the previous pair stays shown). */
  spec: QuerySpec;
  result: QueryResult;
}

/** POST /api/explore (C9); keeps the previous result on screen while a new spec loads. */
export function useExplore(spec: QuerySpec, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    enabled,
    queryKey: ['/api/explore', spec],
    queryFn: async (): Promise<ExploreData> => ({
      spec,
      result: await unwrap(api.POST('/api/explore', { body: spec })),
    }),
    placeholderData: keepPreviousData,
  });
}

export function toTabular(result: QueryResult): TabularData {
  return {
    columns: result.columns.map((c) => ({ key: c.key, label: c.label, type: c.type })),
    rows: result.rows,
  };
}

const ALL = '_all';

/**
 * Chart categories must be unique, but two shooters can share a display name (first-name-only
 * guests are event-scoped new shooters, spec §2). A name held by more than one shooter_id gets
 * the id appended ('Desmond #9'), as race.ts does. Row order is kept, so row i still matches
 * data.rows[i]; the table and CSV keep the raw rows.
 */
function withUniqueShooterNames(data: TabularData): TabularData {
  if (!data.columns.some((c) => c.key === 'shooter')) return data;
  const idsByName = new Map<string, Set<string>>();
  for (const r of data.rows) {
    const name = cellLabel(r.shooter);
    idsByName.set(name, (idsByName.get(name) ?? new Set<string>()).add(cellLabel(r.shooter_id)));
  }
  const shared = new Set([...idsByName].filter(([, ids]) => ids.size > 1).map(([name]) => name));
  return {
    columns: data.columns,
    rows: data.rows.map((r) =>
      shared.has(cellLabel(r.shooter))
        ? { ...r, shooter: `${cellLabel(r.shooter)} #${cellLabel(r.shooter_id)}` }
        : r,
    ),
  };
}

/**
 * 'number' cells (averages, rates) rounded to 2 dp for the chart, as the table prints them:
 * heatmap cell labels and the default tooltips print the raw value (33.243902439024396).
 * The table and CSV keep the raw rows.
 */
export function withRoundedValues(data: TabularData): TabularData {
  const keys = data.columns.filter((c) => c.type === 'number').map((c) => c.key);
  if (keys.length === 0) return data;
  return {
    columns: data.columns,
    rows: data.rows.map((r) => {
      const out = { ...r };
      for (const key of keys) {
        const cell = r[key];
        if (typeof cell === 'number') out[key] = Math.round(cell * 100) / 100;
      }
      return out;
    }),
  };
}

/**
 * Chart option for an explore result: dims[0] on the category/time axis, dims[1] as series.
 * Each dim's label column key equals the dim name (shooter → display name; 'shooter_id' is the id).
 */
export function buildExploreOption(
  data: TabularData,
  groupBy: readonly Dim[],
  chartType: ChartType,
): EChartsOption {
  const chart = withRoundedValues(withUniqueShooterNames(data));
  const [first, second] = groupBy;
  if (first === undefined) {
    const withAll: TabularData = {
      columns: [{ key: ALL, label: '', type: 'string' }, ...chart.columns],
      rows: chart.rows.map((r) => ({ ...r, [ALL]: 'All' })),
    };
    return barOption(withAll, { x: ALL, y: ['value'], labels: true });
  }
  const x: string = first;
  const by = second === undefined ? {} : { seriesBy: second };
  if (chartType === 'heatmap' && second !== undefined) {
    return heatmapOption(chart, {
      x: second,
      y: x,
      value: 'value',
      labels: chart.rows.length <= 150,
    });
  }
  if (chartType === 'line') return lineOption(chart, { x, y: ['value'], ...by, scaleY: true });
  return barOption(chart, { x, y: ['value'], ...by, horizontal: first === 'shooter' });
}

/** The label at `index` in the distinct, first-appearance-ordered labels of column `key`. */
function labelAt(rows: readonly TabularRow[], key: string, index: unknown): string | undefined {
  return typeof index === 'number'
    ? distinct(rows.map((r) => cellLabel(r[key])))[index]
    : undefined;
}

/**
 * The raw result row behind a clicked bar, point or heatmap cell (first dim = category, second =
 * series). A heatmap click carries cell indices, value = [xi, yi, v], into the same distinct label
 * lists heatmapOption draws: the second dim across (x), the first down (y).
 */
export function rowForClick(
  data: TabularData,
  groupBy: readonly Dim[],
  params: { name?: string; seriesName?: string; seriesType?: string; value?: unknown },
): TabularRow | undefined {
  const [first, second] = groupBy;
  if (first === undefined) return data.rows[0];
  const rows = withUniqueShooterNames(data).rows;
  const value: unknown[] = Array.isArray(params.value) ? params.value : [];
  const heatmap = params.seriesType === 'heatmap' && second !== undefined;
  const x = heatmap ? labelAt(rows, first, value[1]) : params.name || String(value[0] ?? '');
  const series = heatmap ? labelAt(rows, second, value[0]) : (params.seriesName ?? '');
  const index = rows.findIndex(
    (r) => cellLabel(r[first]) === x && (second === undefined || cellLabel(r[second]) === series),
  );
  return index === -1 ? undefined : data.rows[index];
}

/**
 * Adds a compare result (Plan 12 `cmp.*`) as a dashed line over the main chart: on a category
 * axis aligned by the first dim's label, on a time axis as its own points. The main series keep
 * their look. Left out: a result with no first dim (nothing to align), a two-dimension chart (one
 * line cannot stand for several series) and horizontal bars (their value axis is x).
 */
export function withCompare(
  option: EChartsOption,
  compare: TabularData,
  groupBy: readonly Dim[],
  name: string,
): EChartsOption {
  const [first] = groupBy;
  if (first === undefined || groupBy.length > 1 || compare.rows.length === 0) return option;
  const axis = (Array.isArray(option.xAxis) ? option.xAxis[0] : option.xAxis) as
    { type?: string; data?: unknown[] } | undefined;
  const rounded = withRoundedValues(compare);
  const style = { type: 'line' as const, name, lineStyle: { type: 'dashed' as const }, z: 3 };
  let data: LineSeriesOption['data'];
  if (axis?.type === 'category' && Array.isArray(axis.data)) {
    const byLabel = new Map(rounded.rows.map((r) => [cellLabel(r[first]), numeric(r.value)]));
    data = axis.data.map((label) => byLabel.get(String(label)) ?? null);
  } else if (axis?.type === 'time') {
    data = rounded.rows.map(
      (r) => [cellLabel(r[first]), numeric(r.value)] as [string, number | null],
    );
  } else {
    return option;
  }
  const line: LineSeriesOption = { ...style, data };
  return { ...option, series: [...[option.series ?? []].flat(), line] };
}
