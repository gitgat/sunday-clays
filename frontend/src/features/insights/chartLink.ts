import {
  customWindow,
  parseCustomWindow,
  windowCodec,
  type TimeWindow,
} from '../../lib/timeWindowChoice';
import type { InsightChart } from './api';

type Spec = NonNullable<InsightChart['spec']>;

/**
 * The URL an insight's "See the chart" opens (spec §3.6). An insight with dates of its own opens a
 * Custom time window (`w`) of those dates, so the header window never hides the evidence; one
 * without keeps the viewer's window (`viewerWindow`). Never a round-type filter: insights are
 * worked out over every round type (a global `rt` on the current page is not carried over).
 */
export function chartHref(chart: InsightChart, viewerWindow?: TimeWindow | null): string {
  return chart.type === 'explorer'
    ? explorerHref(chart, viewerWindow)
    : pageHref(chart, viewerWindow);
}

/** A Custom window for the two dates, or null when they are not a real span (reversed). */
function spanWindow(from: string, to: string) {
  return parseCustomWindow(customWindow(from, to)) === null ? null : customWindow(from, to);
}

/**
 * The `w` value a link carries: the insight's own dates (`own`), else the viewer's window when the
 * URL names one (an explicit 8W included, so it beats the destination's default). Null = leave `w` out.
 */
function windowValue(own: string | null, viewer: TimeWindow | null | undefined): string | null {
  if (own !== null) return own;
  if (viewer === undefined || viewer === null) return null;
  return windowCodec.serialize(viewer);
}

/** The highlight as `hl` items: dates, `s:{id}` shooters, keys and a `from..to` span. */
export function highlightItems(highlight: InsightChart['highlight']): string[] {
  const list = (key: string) => (highlight[key] ?? []).map(String);
  const span = list('span');
  return [
    ...list('dates'),
    ...list('shooter_ids').map((id) => `s:${id}`),
    ...list('keys'),
    ...(span.length === 2 ? [`${span[0] ?? ''}..${span[1] ?? ''}`] : []),
  ];
}

function setIf(params: URLSearchParams, key: string, value: string | null | undefined) {
  if (value !== null && value !== undefined && value !== '') params.set(key, value);
}

/** The Explorer query string for a spec (the keys useExplorerState reads). */
export function explorerParams(spec: Spec, chartType: string | null | undefined) {
  const f = spec.filters;
  const params = new URLSearchParams();
  params.set('m', spec.metric);
  params.set('a', spec.agg);
  params.set('g', spec.group_by.join(','));
  if (f.shooter_ids.length > 0) params.set('sh', f.shooter_ids.join(','));
  if (f.min_rounds > 0) params.set('mr', String(f.min_rounds));
  if (f.best_round_only) params.set('best', '1');
  if (f.min_score !== null && f.min_score !== undefined) params.set('ms', String(f.min_score));
  setIf(params, 'ytd', f.ytd);
  if (spec.sort !== 'key_asc') params.set('s', spec.sort);
  setIf(params, 'c', chartType);
  return params;
}

function explorerHref(chart: InsightChart, viewer: TimeWindow | null | undefined): string {
  if (chart.spec === null || chart.spec === undefined) {
    const bare = windowValue(null, viewer);
    return bare === null ? '/explorer' : `/explorer?${new URLSearchParams({ w: bare }).toString()}`;
  }
  const params = explorerParams(chart.spec, chart.chart_type);
  const f = chart.spec.filters;
  const dated = f.date_from !== null || f.date_to !== null;
  // A one-sided span borrows the missing end from the insight's own window.
  const own = dated
    ? spanWindow(f.date_from ?? chart.window.from, f.date_to ?? chart.window.to)
    : null;
  setIf(params, 'w', windowValue(own, viewer));
  const hl = highlightItems(chart.highlight);
  if (hl.length > 0) params.set('v.hl', hl.join(','));
  if (chart.ref !== null && chart.ref !== undefined) params.set('v.ref', String(chart.ref));
  const compare = chart.compare;
  if (compare !== null && compare !== undefined) {
    if (compare.metric !== chart.spec.metric) params.set('cmp.m', compare.metric);
    if (compare.agg !== chart.spec.agg) params.set('cmp.a', compare.agg);
    // Always written, empty for "everyone": its presence is what turns the comparison on.
    params.set('cmp.sh', compare.filters.shooter_ids.join(','));
    if (compare.filters.best_round_only) params.set('cmp.best', '1');
  }
  return `/explorer?${params.toString()}`;
}

/**
 * Link params that set the page itself rather than one chart. `metric` picks the leaderboard,
 * `era` the stations view and `period` the race's points rule; the leaderboards take their range
 * from the header window, so insight links do not send `period` there.
 */
const PAGE_KEYS = new Set(['metric', 'period', 'era']);

function pageHref(chart: InsightChart, viewer: TimeWindow | null | undefined): string {
  const anchor = chart.anchor ?? '';
  const params = new URLSearchParams();
  const hl = highlightItems(chart.highlight);
  if (hl.length > 0) params.set(`${anchor}.hl`, hl.join(','));
  params.set(`${anchor}.from`, chart.window.from);
  params.set(`${anchor}.to`, chart.window.to);
  setIf(params, 'w', windowValue(spanWindow(chart.window.from, chart.window.to), viewer));
  if (chart.ref !== null && chart.ref !== undefined) params.set(`${anchor}.ref`, String(chart.ref));
  for (const [key, value] of Object.entries(chart.params)) {
    // `metric`/`period` pick the leaderboard and `era` the stations view; the rest are the
    // chart's own options.
    params.set(PAGE_KEYS.has(key) ? key : `${anchor}.${key}`, value);
  }
  return `${chart.route ?? '/'}?${params.toString()}#chart-${anchor}`;
}
