// Query-free half of the time window (codec, labels, ranges), safe for UI primitives to import.
import type { EChartsOption } from 'echarts';
import { useMemo } from 'react';
import { useLocation, useSearchParams } from 'react-router';
import { formatDate } from './format';
import { enumCodec, isoDateCodec, useUrlState, type Codec } from './useUrlState';

export const TIME_WINDOWS = ['8w', '3m', '6m', '12m', 'ytd', 'all'] as const;
export type TimeWindowPreset = (typeof TIME_WINDOWS)[number];
/** `YYYY-MM-DD..YYYY-MM-DD`: a start and an end date the viewer picked (both inclusive). */
export type CustomWindow = `${string}..${string}`;
export type TimeWindow = TimeWindowPreset | CustomWindow;

/** Shown when `?w=` is absent or unknown; the default is never written to the URL. */
export const DEFAULT_WINDOW: TimeWindowPreset = '8w';

/**
 * Pages that open on a longer window than 8W (weather patterns and the race need more Sundays).
 * A page default applies only while the URL has no `w`; keyed by pathname.
 */
const PAGE_DEFAULT_WINDOWS: Readonly<Record<string, TimeWindowPreset>> = {
  '/weather': '12m',
  '/race': '12m',
};

/** The window a page shows when the URL has no `w`. */
export function pageDefaultWindow(pathname: string): TimeWindowPreset {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname;
  return PAGE_DEFAULT_WINDOWS[path] ?? DEFAULT_WINDOW;
}

/** The current page's default window (for converting legacy links, which name no window). */
export function usePageDefaultWindow(): TimeWindowPreset {
  return pageDefaultWindow(useLocation().pathname);
}

export const WINDOW_LABELS: Record<TimeWindowPreset, string> = {
  '8w': 'Last 8 weeks',
  '3m': 'Last 3 months',
  '6m': 'Last 6 months',
  '12m': 'Last 12 months',
  ytd: 'This year to date',
  all: 'All time',
};

/** Compact labels for the filter's buttons. */
export const WINDOW_SHORT_LABELS: Record<TimeWindowPreset, string> = {
  '8w': '8W',
  '3m': '3M',
  '6m': '6M',
  '12m': '12M',
  ytd: 'YTD',
  all: 'All',
};

/** The short label of the Custom control in the filter. */
export const CUSTOM_SHORT_LABEL = 'Custom';

export function isCustomWindow(w: TimeWindow): w is CustomWindow {
  return w.includes('..');
}

export function customWindow(from: string, to: string): CustomWindow {
  return `${from}..${to}`;
}

/** The dates of a custom value: both real calendar dates, from on or before to; otherwise null. */
export function parseCustomWindow(w: string): { from: string; to: string } | null {
  const parts = w.split('..');
  if (parts.length !== 2) return null;
  const from = isoDateCodec.parse(parts[0] as string);
  const to = isoDateCodec.parse(parts[1] as string);
  return from !== null && to !== null && from <= to ? { from, to } : null;
}

/** The dates of a custom window; windowCodec only ever yields valid ones, so this never misses. */
function customDates(w: CustomWindow): { from: string; to: string } {
  return parseCustomWindow(w) as { from: string; to: string };
}

const presetCodec = enumCodec(TIME_WINDOWS);

/**
 * The `w` query parameter: a preset or a valid custom range; anything else (an unknown preset, a
 * reversed or impossible range) reads as the default.
 */
export const windowCodec: Codec<TimeWindow> = {
  parse: (raw) =>
    presetCodec.parse(raw) ?? (parseCustomWindow(raw) === null ? null : (raw as CustomWindow)),
  serialize: (w) => w,
};

export interface WindowRange {
  /** Inclusive first date (YYYY-MM-DD); null = from the beginning. */
  from: string | null;
  /** Inclusive last date: the anchor, or a custom window's end. */
  to: string;
}

const ISO_DAY = /^\d{4}-\d{2}(-\d{2})?$/;
const MONTHS: Partial<Record<TimeWindowPreset, number>> = { '3m': 3, '6m': 6, '12m': 12 };

function pad(n: number, width = 2): string {
  return String(n).padStart(width, '0');
}

/** anchor minus `months` calendar months (day clamped to the shorter month) plus one day. */
function monthsBack(anchor: string, months: number): string {
  const [y = 0, m = 1, d = 1] = anchor.split('-').map(Number);
  const index = y * 12 + (m - 1) - months;
  const year = Math.floor(index / 12);
  const month = index % 12;
  const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const shifted = new Date(Date.UTC(year, month, Math.min(d, lastDay) + 1));
  return `${pad(shifted.getUTCFullYear(), 4)}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())}`;
}

/** anchor minus `days` days, as YYYY-MM-DD. */
export function daysBack(anchor: string, days: number): string {
  const [y = 0, m = 1, d = 1] = anchor.split('-').map(Number);
  const shifted = new Date(Date.UTC(y, m - 1, d - days));
  return `${pad(shifted.getUTCFullYear(), 4)}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())}`;
}

/** The last 8 Sundays: 56 days ending on the anchor (the same window as the "season" boards). */
export const EIGHT_WEEK_DAYS = 56;

/**
 * The dates a window covers, counted back from `anchor` (the latest scored Sunday, never the
 * wall clock): 8w = the 56 days ending at the anchor (its last 8 Sundays); 3/6/12 months = anchor
 * minus N calendar months plus a day; ytd = Jan 1 of the anchor's year; all = no lower bound.
 */
export function windowRange(w: TimeWindow, anchor: string): WindowRange {
  if (isCustomWindow(w)) return customDates(w);
  if (w === '8w') return { from: daysBack(anchor, EIGHT_WEEK_DAYS - 1), to: anchor };
  const months = MONTHS[w];
  if (months !== undefined) return { from: monthsBack(anchor, months), to: anchor };
  if (w === 'ytd') return { from: `${anchor.slice(0, 4)}-01-01`, to: anchor };
  return { from: null, to: anchor };
}

export function windowLabel(w: TimeWindow): string {
  if (!isCustomWindow(w)) return WINDOW_LABELS[w];
  const { from, to } = customDates(w);
  return `${formatDate(from)} – ${formatDate(to)}`;
}

/** "the last 8 weeks", "this year to date", "all time", or a custom window's dates: fits after "in". */
export function windowPhrase(w: TimeWindow): string {
  if (isCustomWindow(w)) return windowLabel(w);
  const label = WINDOW_LABELS[w];
  return label.startsWith('Last') ? `the ${label.toLowerCase()}` : label.toLowerCase();
}

/** "in the last 8 weeks"; for the whole history, "on record". */
export function inWindow(w: TimeWindow): string {
  return w === 'all' ? 'on record' : `in ${windowPhrase(w)}`;
}

/** Rows whose `dateKey` (YYYY-MM-DD) lies inside the range; rows without a date are dropped. */
export function filterRowsByWindow<R extends Record<string, unknown>>(
  rows: readonly R[],
  dateKey: string,
  range: WindowRange,
): R[] {
  return rows.filter((row) => {
    const d = row[dateKey];
    if (typeof d !== 'string') return false;
    const day = d.slice(0, 10);
    return (range.from === null || day >= range.from) && day <= range.to;
  });
}

/**
 * Sets the initial zoom of a date x axis (time, or category of ISO dates) to the range; withZoom
 * keeps it. Untouched for an unbounded range or an axis that is not a date axis.
 */
export function zoomToWindow(option: EChartsOption, range: WindowRange): EChartsOption {
  const { from } = range;
  if (from === null) return option;
  const axis: unknown = Array.isArray(option.xAxis) ? option.xAxis[0] : option.xAxis;
  const { type, data } = (axis ?? {}) as { type?: string; data?: unknown };
  if (type === 'time') {
    return { ...option, dataZoom: [{ type: 'inside', startValue: from, endValue: range.to }] };
  }
  if (type === 'category' && Array.isArray(data)) {
    // Only date (or month) categories zoom: score or station categories ("22", "5") are not dates.
    // A month category is compared on the month, so it stays in when the range touches it.
    const days = data.map((d) =>
      typeof d === 'string' && ISO_DAY.test(d.slice(0, 10)) ? d.slice(0, 10) : '',
    );
    const lo = (d: string) => (d.length === 7 ? from.slice(0, 7) : from);
    const hi = (d: string) => (d.length === 7 ? range.to.slice(0, 7) : range.to);
    const start = days.findIndex((d) => d !== '' && d >= lo(d));
    const end = days.findLastIndex((d) => d !== '' && d <= hi(d));
    if (start === -1 || end < start) return option;
    return { ...option, dataZoom: [{ type: 'inside', startValue: start, endValue: end }] };
  }
  return option;
}

/** The chosen window alone (URL state; the page's default when the URL has no `w`). */
export function useWindowChoice(): [TimeWindow, (next: TimeWindow) => void] {
  // The page's own default (Weather opens on 12M); picking it writes nothing, any other choice
  // (8W included) is written, so the URL stays the source of truth.
  return useUrlState('w', windowCodec, pageDefaultWindow(useLocation().pathname));
}

/**
 * The window the URL names, or null when it has no (valid) `w`. In-app links carry this and never
 * the effective window, so a page's own default (Weather's 12M) stays on its page while an explicit
 * choice, 8W included, travels.
 */
export function useExplicitWindow(): TimeWindow | null {
  const [params] = useSearchParams();
  const raw = params.get('w');
  return useMemo(() => (raw === null ? null : windowCodec.parse(raw)), [raw]);
}
