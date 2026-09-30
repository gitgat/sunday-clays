import type { EChartsOption } from 'echarts';
import { useCallback, useEffect, useMemo } from 'react';
import { useLocation, useSearchParams } from 'react-router';
import { colors } from '../../theme/tokens';
import type { WindowRange } from '../../lib/timeWindowChoice';
import type { TabularRow } from './types';

/**
 * A chart an insight links to (Plan 12, spec §3.6): `?{urlKey}.hl=…&{urlKey}.from=…&{urlKey}.to=…`
 * plus `#chart-{urlKey}`. `hl` items are category labels or dates, `a..b` date spans, or `s:{id}`
 * shooters (mapped to labels by the page). Every other `{urlKey}.{name}` is a page option (`line`,
 * `ref`, `view`, `at`, …).
 */
export interface ChartTarget {
  hl: string[];
  window: WindowRange | null;
  ref: number | null;
  params: Readonly<Record<string, string>>;
  /** True when the link highlights, dates or marks anything (page options alone are not a target). */
  active: boolean;
}

const DATE = /^\d{4}-\d{2}-\d{2}$/;
const TARGET_KEYS = new Set(['hl', 'from', 'to', 'ref']);

export function readTarget(search: URLSearchParams, urlKey: string): ChartTarget {
  const prefix = `${urlKey}.`;
  const params: Record<string, string> = {};
  for (const [key, value] of search) {
    if (!key.startsWith(prefix)) continue;
    const name = key.slice(prefix.length);
    if (name === 'v') continue; // ChartCard's own view flags
    if (!TARGET_KEYS.has(name)) params[name] = value;
  }
  const hl = (search.get(`${prefix}hl`) ?? '').split(',').filter((item) => item !== '');
  const from = search.get(`${prefix}from`);
  const to = search.get(`${prefix}to`);
  const window =
    from !== null && to !== null && DATE.test(from) && DATE.test(to) && from <= to
      ? { from, to }
      : null;
  const refRaw = search.get(`${prefix}ref`);
  const ref =
    refRaw === null || refRaw === '' || !Number.isFinite(Number(refRaw)) ? null : Number(refRaw);
  const active = hl.length > 0 || window !== null || ref !== null;
  return { hl, window, ref, params, active };
}

/** The chart's target from the URL, and `clear` to drop it (back to the page's own view; page
 * options such as `line` stay). */
export function useChartTarget(urlKey: string): { target: ChartTarget; clear: () => void } {
  const [search, setSearch] = useSearchParams();
  const target = useMemo(() => readTarget(search, urlKey), [search, urlKey]);
  const clear = useCallback(() => {
    setSearch(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const name of TARGET_KEYS) next.delete(`${urlKey}.${name}`);
        return next;
      },
      { replace: true },
    );
  }, [setSearch, urlKey]);
  return { target, clear };
}

/** The window a chart shows: the insight's own dates when the link carries them, else the page's. */
export function useTargetWindow(urlKey: string, pageRange: WindowRange | null): WindowRange | null {
  const { target } = useChartTarget(urlKey);
  return target.window ?? pageRange;
}

/** Whether `label` (a category or an x value) is one of the highlighted keys. */
export function matches(keys: readonly string[], label: string): boolean {
  const day = label.slice(0, 10);
  return keys.some((key) => {
    if (key === label || key === day) return true;
    const span = /^(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})$/.exec(key);
    return span !== null && DATE.test(day) && day >= (span[1] ?? '') && day <= (span[2] ?? '');
  });
}

/** `s:{id}` keys as the labels of the rows with that shooter id (other keys pass through). */
export function shooterLabels(labelKey: string, idKey = 'shooter_id') {
  return (keys: readonly string[], rows: readonly TabularRow[]): string[] =>
    keys.flatMap((key) => {
      if (!key.startsWith('s:')) return [key];
      const id = key.slice(2);
      return rows.filter((r) => String(r[idKey]) === id).map((r) => String(r[labelKey] ?? ''));
    });
}

/**
 * Whether a table row is one an insight points to. Each kind of key the link carries must match:
 * its dates or spans (against `date`) and its `s:{id}` shooters (against `shooterId`).
 */
export function rowTargeted(
  keys: readonly string[],
  shooterId: number,
  date: string | null,
): boolean {
  const ids = keys.filter((k) => k.startsWith('s:'));
  const dates = keys.filter((k) => !k.startsWith('s:'));
  if (ids.length === 0 && dates.length === 0) return false;
  const idOk = ids.length === 0 || ids.includes(`s:${String(shooterId)}`);
  const dateOk = dates.length === 0 || (date !== null && matches(dates, date));
  return idOk && dateOk;
}

const HIGHLIGHT = {
  color: colors.text,
  borderColor: colors.accent,
  borderWidth: 3,
} as const;

type Item = unknown;

function categoryAxis(option: EChartsOption): { horizontal: boolean; data: string[] } | null {
  const first = (axis: unknown): { type?: string; data?: unknown } =>
    ((Array.isArray(axis) ? axis[0] : axis) ?? {}) as { type?: string; data?: unknown };
  const x = first(option.xAxis);
  const y = first(option.yAxis);
  if (x.type === 'category' && Array.isArray(x.data)) {
    return { horizontal: false, data: x.data.map(String) };
  }
  if (y.type === 'category' && Array.isArray(y.data)) {
    return { horizontal: true, data: y.data.map(String) };
  }
  return null;
}

/** A data item's label: its `name` (scatter points carry their date), its x value, or the axis category. */
function labelOf(item: Item, category: string | undefined): string {
  if (Array.isArray(item)) return String(item[0]);
  if (item !== null && typeof item === 'object' && 'name' in item) {
    return String((item as { name: unknown }).name);
  }
  return category ?? '';
}

function mark(item: Item): Item {
  if (item !== null && typeof item === 'object' && !Array.isArray(item)) {
    return { ...(item as object), itemStyle: HIGHLIGHT };
  }
  return { value: item, itemStyle: HIGHLIGHT };
}

type SeriesLike = {
  type?: string;
  data?: unknown;
  lineStyle?: { opacity?: number };
  markLine?: unknown;
  markPoint?: { data?: unknown[] };
};

/** Line and scatter series get a ring drawn as a markPoint: it shows even when the line draws no symbols. */
const isPointSeries = (s: SeriesLike) => s.type === 'line' || s.type === 'scatter';
/** Invisible helpers (a band's stacked edges) are never marked. */
const isHelper = (s: SeriesLike) => s.lineStyle?.opacity === 0;

/** Where a data item sits on the chart, or null when it has no value. */
function coordOf(item: Item, category: string | undefined): unknown[] | null {
  const value =
    item !== null && typeof item === 'object' && !Array.isArray(item)
      ? (item as { value?: unknown }).value
      : item;
  const coord = Array.isArray(value) ? value : [category, value];
  return coord[1] === null || coord[1] === undefined ? null : [coord[0], coord[1]];
}

/**
 * Draws the highlighted bars in the text colour with an accent ring, the highlighted line and
 * scatter points as ringed marks (on the first visible series only, so a date is ringed once), and
 * the reference value as a dashed line. Pure: the builders' option is never mutated.
 */
export function applyTarget(
  option: EChartsOption,
  labels: readonly string[],
  ref: number | null,
): EChartsOption {
  if (labels.length === 0 && ref === null) return option;
  const axis = categoryAxis(option);
  const list = [option.series ?? []].flat() as SeriesLike[];
  const primary = list.findIndex((s) => !isHelper(s));
  const primaryPoints = list.findIndex((s) => !isHelper(s) && isPointSeries(s));
  const series = list.map((one, index) => {
    let data = one.data;
    let markPoint = one.markPoint;
    if (labels.length > 0 && Array.isArray(data)) {
      const hit = (item: Item, i: number): boolean => {
        const x = labelOf(item, axis === null ? undefined : axis.data[i]);
        return x !== '' && matches(labels, x);
      };
      if (!isPointSeries(one)) {
        data = data.map((item: Item, i: number) => (hit(item, i) ? mark(item) : item));
      } else if (index === primaryPoints) {
        const rings = data.flatMap((item: Item, i: number) => {
          const coord = hit(item, i) ? coordOf(item, axis?.data[i]) : null;
          return coord === null
            ? []
            : [{ coord, symbol: 'circle', symbolSize: 12, itemStyle: HIGHLIGHT }];
        });
        markPoint = {
          ...one.markPoint,
          silent: true,
          label: { show: false },
          data: [...(one.markPoint?.data ?? []), ...rings],
        } as SeriesLike['markPoint'];
      }
    }
    const markLine =
      ref !== null && index === primary
        ? {
            symbol: 'none',
            silent: true,
            lineStyle: { type: 'dashed' as const, color: colors.accent },
            label: { show: true, formatter: String(ref) },
            data: [axis?.horizontal === true ? { xAxis: ref } : { yAxis: ref }],
          }
        : one.markLine;
    return {
      ...one,
      data,
      ...(markPoint === undefined ? {} : { markPoint }),
      ...(markLine === undefined ? {} : { markLine }),
    };
  });
  return { ...option, series: series as EChartsOption['series'] };
}

const ringed = (item: Item): boolean =>
  item !== null &&
  typeof item === 'object' &&
  (item as { itemStyle?: unknown }).itemStyle === HIGHLIGHT;

/** How many marks `applyTarget` drew (ringed bars and points); ChartFrame shows it as `data-marked` (e2e reads it). */
export function markedCount(option: EChartsOption): number {
  return ([option.series ?? []].flat() as SeriesLike[])
    .flatMap((s) => [
      ...(Array.isArray(s.data) ? (s.data as Item[]) : []),
      ...(s.markPoint?.data ?? []),
    ])
    .filter(ringed).length;
}

/** Scrolls to and focuses `#chart-{urlKey}` once, when the URL's hash names it. */
export function useScrollToTarget(urlKey: string, ready: boolean): void {
  const { hash } = useLocation();
  useEffect(() => {
    if (!ready || hash !== `#chart-${urlKey}`) return;
    const el = document.getElementById(`chart-${urlKey}`);
    if (el === null) return;
    el.scrollIntoView?.({ block: 'start' }); // Card's scroll-mt clears the sticky top bar
    el.focus({ preventScroll: true });
  }, [hash, urlKey, ready]);
}
