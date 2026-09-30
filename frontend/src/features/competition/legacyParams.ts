import type { TimeWindow, TimeWindowPreset } from '../../lib/timeWindowChoice';
import { customWindow } from '../../lib/timeWindowChoice';
import { isoDateCodec } from '../../lib/useUrlState';
import type { Conversion, ParamUpdates } from '../../lib/useLegacyParams';

/** What a page's converters may need from /api/meta (null until it answers). */
export interface LegacyContext {
  firstSunday: string | null;
  lastSunday: string | null;
  /** The page's own default window: written as "no `w`". */
  pageDefault: TimeWindowPreset;
}

/** The old "rating" and "most improved" boards are now one: rating gain. */
export function convertLegacyMetric(params: URLSearchParams): ParamUpdates {
  const metric = params.get('metric');
  return metric === 'rating' || metric === 'most_improved' ? { metric: 'rating_gain' } : {};
}

/** A `w` update: the page default is written as no `w` at all. */
function windowUpdate(w: TimeWindow, ctx: LegacyContext): ParamUpdates {
  return { w: w === ctx.pageDefault ? null : w };
}

const date = (raw: string | null): string | null => (raw === null ? null : isoDateCodec.parse(raw));

/** `since..until` when both are real dates in order; otherwise null. */
function range(from: string | null, to: string | null): TimeWindow | null {
  return from !== null && to !== null && from <= to ? customWindow(from, to) : null;
}

function merge(...parts: ParamUpdates[]): Conversion {
  const out: Record<string, string | null> = Object.assign({}, ...parts);
  return Object.keys(out).length === 0 ? null : out;
}

const BOARD_PERIODS: Record<string, TimeWindowPreset> = {
  season: '8w',
  ytd: 'ytd',
  rolling_12: '12m',
  all_time: 'all',
};

/**
 * Leaderboards: `period=season|ytd|rolling_12|all_time` become `w=8w|ytd|12m|all`; `period=custom` with
 * `since` (Jan 1 of the end year when absent) and `as_of` (the latest Sunday when absent) become
 * `w=since..as_of`. `period` and `since` are then removed. `as_of` stays: it is the "Board as of" date.
 * An explicit `w` always wins. `metric=rating|most_improved` become `rating_gain`.
 */
export function convertLegacyBoard(params: URLSearchParams, ctx: LegacyContext): Conversion {
  const metric = convertLegacyMetric(params);
  if (!params.has('period') && !params.has('since')) return merge(metric);
  const cleanup: ParamUpdates = { period: null, since: null };
  const period = params.get('period');
  if (params.has('w')) return merge(metric, cleanup);
  if (period === 'custom') {
    const end = date(params.get('as_of')) ?? ctx.lastSunday;
    if (end === null) return 'wait';
    const start = date(params.get('since')) ?? `${end.slice(0, 4)}-01-01`;
    const w = range(start, end);
    return merge(metric, cleanup, w === null ? {} : { ...windowUpdate(w, ctx), as_of: null });
  }
  const preset = period === null ? undefined : BOARD_PERIODS[period];
  return merge(metric, cleanup, preset === undefined ? {} : windowUpdate(preset, ctx));
}

const RECORD_MODES: Record<string, TimeWindowPreset> = { all: 'all', ytd: 'ytd' };

/**
 * Records: `rp=all|ytd` become `w=all|ytd`; `rp=custom` with `since` (the first Sunday when absent) and
 * `as_of` (the latest Sunday when absent) become `w=since..as_of`. `rp`, `since` and `as_of` are then
 * removed (Records has no "Board as of"). An explicit `w` always wins.
 */
export function convertLegacyRecords(params: URLSearchParams, ctx: LegacyContext): Conversion {
  if (!params.has('rp') && !params.has('since') && !params.has('as_of')) return null;
  const cleanup: ParamUpdates = { rp: null, since: null, as_of: null };
  const rp = params.get('rp');
  if (params.has('w')) return merge(cleanup);
  if (rp === 'custom') {
    const start = date(params.get('since')) ?? ctx.firstSunday;
    const end = date(params.get('as_of')) ?? ctx.lastSunday;
    if (start === null || end === null) return 'wait';
    const w = range(start, end);
    return merge(cleanup, w === null ? {} : windowUpdate(w, ctx));
  }
  const preset = rp === null ? undefined : RECORD_MODES[rp];
  return merge(cleanup, preset === undefined ? {} : windowUpdate(preset, ctx));
}

/**
 * Race: `since` (with `until`, the latest Sunday when absent) becomes `w=since..until`; `since` and
 * `until` are then removed. `period` stays: it is now the points rule (last 12 months, last 8 Sundays,
 * since Jan 1), and it no longer chooses the replayed Sundays. An explicit `w` always wins.
 * `metric=rating|most_improved` become `rating_gain`.
 */
export function convertLegacyRace(params: URLSearchParams, ctx: LegacyContext): Conversion {
  // `period=custom` was the old custom-dates mode, not a points rule.
  const metric: ParamUpdates = {
    ...convertLegacyMetric(params),
    ...(params.get('period') === 'custom' ? { period: null } : {}),
  };
  if (!params.has('since') && !params.has('until')) return merge(metric);
  const cleanup: ParamUpdates = { since: null, until: null };
  if (params.has('w')) return merge(metric, cleanup);
  const start = date(params.get('since'));
  if (start === null) return merge(metric, cleanup);
  const end = date(params.get('until')) ?? ctx.lastSunday;
  if (end === null) return 'wait';
  const w = range(start, end);
  return merge(metric, cleanup, w === null ? {} : windowUpdate(w, ctx));
}
