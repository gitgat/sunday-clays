import {
  AGGS,
  DIMS,
  METRICS,
  querySpec,
  type Agg,
  type Dim,
  type Metric,
  type QuerySpec,
} from '../../components/charts/explore';
import type { ChartType } from '../../components/charts/types';
import { useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router';
import { THIN_WINDOW_SUNDAYS } from '../../components/ThinWindowNudge';
import { useRoundTypes } from '../../lib/roundTypes';
import {
  customWindow,
  parseCustomWindow,
  useMeta,
  useTimeWindow,
  windowLabel,
  type CustomWindow,
  type WindowRange,
} from '../../lib/timeWindow';
import {
  boolCodec,
  enumCodec,
  isoDateCodec,
  listCodec,
  rangeCodec,
  useSetUrlParams,
  useUrlState,
  type Codec,
} from '../../lib/useUrlState';

export const STATUSES = ['member', 'guest', 'deceased'] as const;
/** Normalized gauge classes (C3) plus 'unspecified' for "not recorded" (C7). */
export const GAUGES = [
  '12 Gauge',
  '20 Gauge',
  '28 Gauge',
  '.410',
  'Sub-Gauge',
  'SxS',
  'unspecified',
] as const;
export const SORTS = ['key_asc', 'key_desc', 'value_desc', 'value_asc'] as const;
export const CHART_TYPES: ChartType[] = ['bar', 'line', 'heatmap'];
/** Metrics whose values are combined with the chosen aggregate (the rest are counts/rates). */
export const AGGREGATED_METRICS: readonly Metric[] = [
  'score',
  'adjusted',
  'residual',
  'rating',
  'attendance',
];

export type RangeFilter = 'temp_f' | 'gust_mph' | 'precip_in';
export const RANGE_FILTERS: Record<
  RangeFilter,
  { param: string; label: string; min: number; max: number; step: number; unit: string }
> = {
  temp_f: { param: 't', label: 'Temperature', min: 0, max: 110, step: 1, unit: '°F' },
  gust_mph: { param: 'gu', label: 'Wind gust', min: 0, max: 50, step: 1, unit: 'mph' },
  precip_in: { param: 'p', label: 'Rain', min: 0, max: 2, step: 0.01, unit: 'in' },
};

/** Empty string ⇄ null, so "no filter" drops the parameter. */
function optional<T>(codec: Codec<T>): Codec<T | null> {
  return {
    parse: (raw) => (raw === '' ? null : codec.parse(raw)),
    serialize: (value) => (value === null ? '' : codec.serialize(value)),
  };
}

const countCodec: Codec<number> = {
  parse: (raw) => (/^\d{1,4}$/.test(raw) ? Number(raw) : null),
  serialize: String,
};
/**
 * Shooter ids: positive integers of at most 9 digits, written without leading zeros, so an id
 * the server would reject (0, 1e23, a 400-digit Infinity) is dropped here like any malformed item.
 */
const idsCodec = listCodec<number>({
  parse: (raw) => (/^[1-9]\d{0,8}$/.test(raw) ? Number(raw) : null),
  serialize: String,
});
const dateCodec = optional(isoDateCodec);
/** `ms`: rounds at or over this score only (Plan 12), 0-50. */
const minScoreCodec = optional<number>({
  parse: (raw) => (/^\d{1,2}$/.test(raw) && Number(raw) <= 50 ? Number(raw) : null),
  serialize: String,
});
/** `ytd`: each year cut at the same month-day (Plan 12), MM-DD. */
const ytdCodec = optional<string>({
  parse: (raw) => (/^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/.test(raw) ? raw : null),
  serialize: (v) => v,
});
const rangeParam = optional(rangeCodec);

const DEFAULT_DIMS: Dim[] = ['year'];
/** What a window of fewer Sundays than THIN_WINDOW_SUNDAYS opens on: one year would be a single bar. */
const SUNDAY_DIMS: Dim[] = ['event'];
const NO_STATUSES: (typeof STATUSES)[number][] = [];
const NO_GAUGES: (typeof GAUGES)[number][] = [];
const NO_IDS: number[] = [];

const codecs = {
  metric: enumCodec<Metric>(METRICS),
  agg: enumCodec<Agg>(AGGS),
  dims: listCodec(enumCodec<Dim>(DIMS)),
  statuses: listCodec(enumCodec(STATUSES)),
  gauges: listCodec(enumCodec(GAUGES)),
  sort: enumCodec(SORTS),
  chart: enumCodec(CHART_TYPES),
  metricOrNull: optional(enumCodec<Metric>(METRICS)),
  aggOrNull: optional(enumCodec<Agg>(AGGS)),
};

/**
 * A second series to compare with (Plan 12 insight links): the same query with `cmp.m`, `cmp.a`,
 * `cmp.sh` and `cmp.best` swapped in. Present when any `cmp.` key is; `cmp.sh` absent = everyone.
 */
export const COMPARE_KEYS = ['cmp.m', 'cmp.a', 'cmp.sh', 'cmp.best'] as const;

const DAY_MS = 86_400_000;

/** Sundays on the calendar from `from` to `to`, both inclusive. */
export function sundaysBetween(from: string, to: string): number {
  const start = Date.parse(`${from}T00:00:00Z`);
  const end = Date.parse(`${to}T00:00:00Z`);
  const firstSunday = start + ((7 - new Date(start).getUTCDay()) % 7) * DAY_MS;
  return firstSunday > end ? 0 : Math.floor((end - firstSunday) / (7 * DAY_MS)) + 1;
}

/** The window an old `from`/`to` link means: a missing end is the first or latest scored Sunday. */
export function legacyWindow(
  from: string | null,
  to: string | null,
  firstDate: string | null | undefined,
  lastDate: string | null | undefined,
): CustomWindow | null {
  const start = from ?? firstDate ?? null;
  const end = to ?? lastDate ?? null;
  if ((from === null && to === null) || start === null || end === null) return null;
  return parseCustomWindow(customWindow(start, end)) === null ? null : customWindow(start, end);
}

/** The whole Explorer query lives in the URL, so any view is a shareable link. */
export function useExplorerState() {
  const [metric, setMetric] = useUrlState('m', codecs.metric, 'score');
  const [agg, setAgg] = useUrlState('a', codecs.agg, 'avg');
  // Retired From/To boxes: an old link's dates become a Custom `w` once, and leave the URL.
  const [legacyFrom] = useUrlState('from', dateCodec, null);
  const [legacyTo] = useUrlState('to', dateCodec, null);
  const [statuses, setStatuses] = useUrlState('st', codecs.statuses, NO_STATUSES);
  const [gauges, setGauges] = useUrlState('ga', codecs.gauges, NO_GAUGES);
  const [shooterIds, setShooterIds] = useUrlState('sh', idsCodec, NO_IDS);
  const [temp, setTemp] = useUrlState(RANGE_FILTERS.temp_f.param, rangeParam, null);
  const [gust, setGust] = useUrlState(RANGE_FILTERS.gust_mph.param, rangeParam, null);
  const [precip, setPrecip] = useUrlState(RANGE_FILTERS.precip_in.param, rangeParam, null);
  const [minRounds, setMinRounds] = useUrlState('mr', countCodec, 0);
  const [bestOnly, setBestOnly] = useUrlState('best', boolCodec, false);
  const [sort, setSort] = useUrlState('s', codecs.sort, 'key_asc');
  const [chartType, setChartType] = useUrlState('c', codecs.chart, 'bar');
  const [minScore, setMinScore] = useUrlState('ms', minScoreCodec, null);
  const [ytd, setYtd] = useUrlState('ytd', ytdCodec, null);
  const [cmpMetric] = useUrlState('cmp.m', codecs.metricOrNull, null);
  const [cmpAgg] = useUrlState('cmp.a', codecs.aggOrNull, null);
  const [cmpShooters] = useUrlState('cmp.sh', idsCodec, NO_IDS);
  const [cmpBest] = useUrlState('cmp.best', boolCodec, false);
  const [params, setParams] = useSearchParams();
  const hasCompare = COMPARE_KEYS.some((key) => params.has(key));
  const clearCompare = useCallback(() => {
    setParams(
      (prev) => {
        const out = new URLSearchParams(prev);
        for (const key of COMPARE_KEYS) out.delete(key);
        return out;
      },
      { replace: true },
    );
  }, [setParams]);
  const [roundTypes] = useRoundTypes();
  const meta = useMeta();
  const window = useTimeWindow();
  const hasLegacy = params.has('from') || params.has('to');
  const movedTo = hasLegacy
    ? legacyWindow(legacyFrom, legacyTo, meta.data?.first_score_date, meta.data?.last_score_date)
    : null;
  // The dates the query covers: the window, or (for one render, until the URL is rewritten) the
  // window an old link's dates stand for.
  const range: WindowRange | null =
    movedTo === null ? window.range : (parseCustomWindow(movedTo) as WindowRange);
  const setUrlParams = useSetUrlParams();
  // A link with one date needs /api/meta for the other end, so it waits for the answer.
  const legacyReady = hasLegacy && (!meta.isPending || (legacyFrom !== null && legacyTo !== null));
  useEffect(() => {
    if (!legacyReady) return;
    setUrlParams({ from: null, to: null, ...(movedTo === null ? {} : { w: movedTo }) });
  }, [legacyReady, movedTo, setUrlParams]);
  // Calendar Sundays, on purpose: it must be known before any events load. The nudge counts scored ones.
  // An open start (All) reaches back to the first scored Sunday.
  const start = range === null ? null : (range.from ?? meta.data?.first_score_date ?? null);
  const thin =
    range !== null && start !== null && sundaysBetween(start, range.to) < THIN_WINDOW_SUNDAYS;
  const [dims, setDims] = useUrlState('g', codecs.dims, thin ? SUNDAY_DIMS : DEFAULT_DIMS);

  const groupBy = dims.slice(0, 2);
  const spec: QuerySpec = querySpec({
    metric,
    agg,
    group_by: groupBy,
    sort,
    filters: {
      date_from: range?.from ?? null,
      date_to: range?.to ?? null,
      shooter_ids: shooterIds,
      round_types: roundTypes,
      statuses: [...statuses],
      gauges: [...gauges],
      temp_f: temp,
      gust_mph: gust,
      precip_in: precip,
      min_rounds: minRounds,
      best_round_only: bestOnly,
      min_score: minScore,
      ytd,
    },
  });
  const compare: QuerySpec | null = hasCompare
    ? {
        ...spec,
        metric: cmpMetric ?? spec.metric,
        agg: cmpAgg ?? spec.agg,
        filters: { ...spec.filters, shooter_ids: cmpShooters, best_round_only: cmpBest },
      }
    : null;
  const ranges: Record<
    RangeFilter,
    [[number, number] | null, (v: [number, number] | null) => void]
  > = {
    temp_f: [temp, setTemp],
    gust_mph: [gust, setGust],
    precip_in: [precip, setPrecip],
  };
  return {
    spec,
    compare,
    /** The dates the query covers (null: nothing scored yet), and whether they are known yet. */
    range,
    settled: !meta.isPending,
    label: windowLabel(movedTo ?? window.window),
    chartType,
    ranges,
    set: {
      metric: setMetric,
      agg: setAgg,
      dims: setDims,
      statuses: setStatuses,
      gauges: setGauges,
      shooterIds: setShooterIds,
      minRounds: setMinRounds,
      bestOnly: setBestOnly,
      sort: setSort,
      chartType: setChartType,
      minScore: setMinScore,
      ytd: setYtd,
      clearCompare,
    },
  };
}
