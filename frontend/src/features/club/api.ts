import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import { useRoundTypes } from '../../lib/roundTypes';
import type { WindowRange } from '../../lib/timeWindowChoice';
import type { paths } from '../../api/schema';

type JsonOf<Op> = Op extends { responses: { 200: { content: { 'application/json': infer R } } } }
  ? R
  : never;

export type ClubSummary = JsonOf<paths['/api/club/summary']['get']>;
export type StatusYear = ClubSummary['status_by_year'][number];
export type AttendancePoint = JsonOf<paths['/api/club/attendance']['get']>[number];
export type Cohort = JsonOf<paths['/api/club/cohorts']['get']>[number];
export type FirstRounds = JsonOf<paths['/api/club/first-rounds']['get']>;
export type DistributionGroup = JsonOf<paths['/api/club/distribution']['get']>[number];
export type Regulars = JsonOf<paths['/api/club/regulars']['get']>;
export type CoreRegular = Regulars['core'][number];
export type LapsedRegular = Regulars['lapsed'][number];
export type ConversionYear = JsonOf<paths['/api/club/conversion']['get']>[number];
export type ParityYear = JsonOf<paths['/api/club/parity']['get']>[number];
export type ClubTrends = JsonOf<paths['/api/club/trends']['get']>;
export type YearTrend = ClubTrends['years'][number];
export type EventTrend = ClubTrends['events'][number];
export type MonthTrend = ClubTrends['months'][number];

/** Core and lapsed regulars as of today (the server resolves `as_of`). */
export function useClubRegulars() {
  return useQuery({
    queryKey: ['/api/club/regulars'],
    queryFn: () => unwrap(api.GET('/api/club/regulars')),
  });
}

/**
 * The headline numbers over the time window (`since`/`as_of`). Accepts the global round-type filter
 * (C8), so it sends it and keys on it (C10). Waits for the window's dates (`range` null).
 */
export function useClubSummary(range: WindowRange | null) {
  const [roundTypes] = useRoundTypes();
  const query = { round_type: roundTypes, since: range?.from ?? undefined, as_of: range?.to };
  return useQuery({
    queryKey: ['/api/club/summary', query],
    queryFn: () => unwrap(api.GET('/api/club/summary', { params: { query } })),
    enabled: range !== null,
  });
}

/** Round counts per calendar year by status: a year-by-year table, so it ignores the time window. */
export function useClubStatusByYear() {
  const [roundTypes] = useRoundTypes();
  const query = { round_type: roundTypes };
  return useQuery({
    queryKey: ['/api/club/summary', query],
    queryFn: () => unwrap(api.GET('/api/club/summary', { params: { query } })),
  });
}

export function useClubAttendance() {
  return useQuery({
    queryKey: ['/api/club/attendance'],
    queryFn: () => unwrap(api.GET('/api/club/attendance')),
  });
}

export function useClubCohorts() {
  return useQuery({
    queryKey: ['/api/club/cohorts'],
    queryFn: () => unwrap(api.GET('/api/club/cohorts')),
  });
}

/** Same key shape as features/shooters' useClubDistribution, so the TanStack cache is shared. */
export function useClubDistribution() {
  const [roundTypes] = useRoundTypes();
  return useQuery({
    queryKey: ['/api/club/distribution', { by: 'year', round_type: roundTypes }],
    queryFn: () =>
      unwrap(
        api.GET('/api/club/distribution', {
          params: { query: { by: 'year', round_type: roundTypes } },
        }),
      ),
  });
}

export function useClubConversion() {
  return useQuery({
    queryKey: ['/api/club/conversion'],
    queryFn: () => unwrap(api.GET('/api/club/conversion')),
  });
}

export function useClubParity() {
  return useQuery({
    queryKey: ['/api/club/parity', { by: 'year' }],
    queryFn: () => unwrap(api.GET('/api/club/parity', { params: { query: { by: 'year' } } })),
  });
}

export function useClubTrends() {
  return useQuery({
    queryKey: ['/api/club/trends'],
    queryFn: () => unwrap(api.GET('/api/club/trends')),
  });
}

/** First-Sunday scores for shooters whose first Sunday is in the window (`null` = not known yet). */
export function useClubFirstRounds(window: WindowRange | null) {
  const query = { from: window?.from ?? undefined, to: window?.to };
  return useQuery({
    queryKey: ['/api/club/first-rounds', query],
    queryFn: () => unwrap(api.GET('/api/club/first-rounds', { params: { query } })),
    enabled: window !== null,
  });
}
