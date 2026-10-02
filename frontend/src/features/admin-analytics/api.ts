import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import { useWindowChoice, windowRange } from '../../lib/timeWindow';
import { windowTagText } from '../../lib/windowText';
import type { JsonOf } from '../admin/api';

export type Visitors = JsonOf<paths['/api/admin/analytics/visitors']['get']>;
export type PageKindViews = JsonOf<paths['/api/admin/analytics/pages']['get']>[number];
export type BumpsSummary = JsonOf<paths['/api/admin/analytics/bumps']['get']>;
export type Uptake = JsonOf<paths['/api/admin/analytics/me-states']['get']>;

/** Local days from `since` (null: from the first data) to `asOf`. */
export interface AnalyticsRange {
  since: string | null;
  asOf: string;
}

/** Today as YYYY-MM-DD in the browser's calendar. */
export function todayIso(now: Date = new Date()): string {
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${String(now.getFullYear())}-${month}-${day}`;
}

/** Every day on record up to `asOf`: what fullscreen and the CSV show. */
export function allTime(asOf: string): AnalyticsRange {
  return { since: null, asOf };
}

/**
 * The header's time window (`w`, default 8 weeks), anchored at today rather than the latest
 * scored Sunday: visits happen every day (Decision 14). `tag` names it with its dates.
 */
export function useAnalyticsRange(): { range: AnalyticsRange; tag: string } {
  const [window] = useWindowChoice();
  const today = todayIso();
  return useMemo(() => {
    const dates = windowRange(window, today);
    return { range: { since: dates.from, asOf: dates.to }, tag: windowTagText(window, dates) };
  }, [window, today]);
}

function params(range: AnalyticsRange) {
  const query =
    range.since === null ? { as_of: range.asOf } : { since: range.since, as_of: range.asOf };
  return { params: { query } };
}

export const visitorsKey = (range: AnalyticsRange) =>
  ['/api/admin/analytics/visitors', range] as const;
export const pagesKey = (range: AnalyticsRange) => ['/api/admin/analytics/pages', range] as const;
export const bumpsKey = (range: AnalyticsRange) => ['/api/admin/analytics/bumps', range] as const;
export const uptakeKey = (range: AnalyticsRange) =>
  ['/api/admin/analytics/me-states', range] as const;

export const fetchVisitors = (range: AnalyticsRange) =>
  unwrap(api.GET('/api/admin/analytics/visitors', params(range)));
export const fetchPages = (range: AnalyticsRange) =>
  unwrap(api.GET('/api/admin/analytics/pages', params(range)));
export const fetchBumps = (range: AnalyticsRange) =>
  unwrap(api.GET('/api/admin/analytics/bumps', params(range)));
export const fetchUptake = (range: AnalyticsRange) =>
  unwrap(api.GET('/api/admin/analytics/me-states', params(range)));

export function useVisitors(range: AnalyticsRange) {
  return useQuery({ queryKey: visitorsKey(range), queryFn: () => fetchVisitors(range) });
}
export function usePages(range: AnalyticsRange) {
  return useQuery({ queryKey: pagesKey(range), queryFn: () => fetchPages(range) });
}
export function useBumps(range: AnalyticsRange) {
  return useQuery({ queryKey: bumpsKey(range), queryFn: () => fetchBumps(range) });
}
export function useUptake(range: AnalyticsRange) {
  return useQuery({ queryKey: uptakeKey(range), queryFn: () => fetchUptake(range) });
}
