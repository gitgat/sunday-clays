import { keepPreviousData, useQuery, type QueryClient } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import { useRoundTypes, type RoundTypeValue } from '../../lib/roundTypes';
import type { WindowRange } from '../../lib/timeWindowChoice';

export type JsonOf<Op> = Op extends {
  responses: { 200: { content: { 'application/json': infer R } } };
}
  ? R
  : never;

export type ShooterListItem = JsonOf<paths['/api/shooters']['get']>[number];
export type ShooterDetail = JsonOf<paths['/api/shooters/{id}']['get']>;
export type Odometer = ShooterDetail['odometer'];
export type PersonalBest = ShooterDetail['pbs'][number];
export type ShooterInsights = JsonOf<paths['/api/shooters/{id}/insights']['get']>;

/** The directory list; keeps the previous rows (`isPlaceholderData`) while a new search or filter loads. */
export function useShooters(q: string, active: boolean) {
  return useQuery({
    queryKey: ['/api/shooters', { q, active }],
    queryFn: () =>
      unwrap(
        api.GET('/api/shooters', {
          params: { query: { q: q || undefined, active: active ? true : undefined } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** The API's `since` / `as_of` for a window (`as_of` is the window's last day). */
const windowQuery = (range: WindowRange | null) => ({
  since: range?.from ?? undefined,
  as_of: range?.to,
});

/**
 * Detail + odometer; appends the global round-type filter (C10) and the time window, which adds
 * `window_stats`. Never waits for the window: with `range` null (meta not loaded, or nothing scored)
 * it asks for lifetime numbers only. Disabled for a non-positive or non-integer id.
 */
export function useShooter(id: number, range: WindowRange | null) {
  const [roundTypes] = useRoundTypes();
  const query = { round_type: roundTypes, ...windowQuery(range) };
  return useQuery({
    queryKey: ['/api/shooters/{id}', id, query],
    queryFn: () => unwrap(api.GET('/api/shooters/{id}', { params: { path: { id }, query } })),
    // A new window keeps this shooter's page on screen while its numbers load; never another shooter's.
    placeholderData: (prev, prevQuery) => (prevQuery?.queryKey[1] === id ? prev : undefined),
    enabled: Number.isInteger(id) && id > 0,
  });
}

export function useShooterInsights(id: number) {
  return useQuery({
    queryKey: ['/api/shooters/{id}/insights', id],
    queryFn: () => unwrap(api.GET('/api/shooters/{id}/insights', { params: { path: { id } } })),
  });
}

export type ShooterRound = JsonOf<paths['/api/shooters/{id}/rounds']['get']>[number];
export type Rating = JsonOf<paths['/api/shooters/{id}/rating']['get']>;
export type RatingPoint = Rating['points'][number];
export type SplitRow = JsonOf<paths['/api/shooters/{id}/splits']['get']>[number];
export type ClubDistributionGroup = JsonOf<paths['/api/club/distribution']['get']>[number];
export type SplitBy =
  'season' | 'month' | 'year' | 'round_type' | 'gauge' | 'temp_band' | 'wind_band' | 'precip_band';

export function useShooterRounds(id: number) {
  const [roundTypes] = useRoundTypes();
  return useQuery({
    queryKey: ['/api/shooters/{id}/rounds', id, { round_type: roundTypes }],
    queryFn: () =>
      unwrap(
        api.GET('/api/shooters/{id}/rounds', {
          params: { path: { id }, query: { round_type: roundTypes } },
        }),
      ),
  });
}

export type EventSummary = JsonOf<paths['/api/events']['get']>[number];

/**
 * The Sundays of `year` the club held (complete results), as ISO dates. Filtered by the global round
 * type like the shooter's rounds are, so "not shot" compares like with like. Shares the home
 * feature's cache entry for the same request (D2).
 */
export function useHeldSundays(year: number) {
  const [roundTypes] = useRoundTypes();
  return useQuery({
    queryKey: ['/api/events', { year, round_type: roundTypes }],
    queryFn: () =>
      unwrap(api.GET('/api/events', { params: { query: { year, round_type: roundTypes } } })),
    select: heldDates,
  });
}

const heldDates = (events: EventSummary[]) =>
  events.filter((e) => e.results_complete).map((e) => e.event_date);

/** The held Sundays of one year, for the calendar's all-years fullscreen and CSV. Reuses the page's cached year (same key as useHeldSundays). */
export async function fetchHeldSundays(
  queryClient: QueryClient,
  year: number,
  roundTypes: RoundTypeValue[],
) {
  const events = await queryClient.ensureQueryData({
    queryKey: ['/api/events', { year, round_type: roundTypes }],
    queryFn: () =>
      unwrap(api.GET('/api/events', { params: { query: { year, round_type: roundTypes } } })),
  });
  return heldDates(events);
}

export function useShooterRating(id: number) {
  return useQuery({
    queryKey: ['/api/shooters/{id}/rating', id],
    queryFn: () => unwrap(api.GET('/api/shooters/{id}/rating', { params: { path: { id } } })),
  });
}

/**
 * Splits over the time window (`range`; null = every round, which the fullscreen table uses).
 * Keeps the previous split on screen while the next one loads, so the chart card (and the chips in
 * it) stays mounted.
 */
export function useShooterSplits(id: number, by: SplitBy, range: WindowRange | null) {
  const [roundTypes] = useRoundTypes();
  const query = { by, round_type: roundTypes, ...windowQuery(range) };
  return useQuery({
    // Only for the same shooter: another shooter's splits must never show under this profile.
    placeholderData: (prev, prevQuery) => (prevQuery?.queryKey[1] === id ? prev : undefined),
    queryKey: ['/api/shooters/{id}/splits', id, query],
    queryFn: () =>
      unwrap(api.GET('/api/shooters/{id}/splits', { params: { path: { id }, query } })),
    enabled: range !== null,
  });
}

/** The same splits over every round: the source of the fullscreen table and the CSV. */
export function fetchAllSplits(
  queryClient: QueryClient,
  id: number,
  by: SplitBy,
  roundTypes: RoundTypeValue[],
) {
  const query = { by, round_type: roundTypes };
  return queryClient.ensureQueryData({
    queryKey: ['/api/shooters/{id}/splits', id, query],
    queryFn: () =>
      unwrap(api.GET('/api/shooters/{id}/splits', { params: { path: { id }, query } })),
  });
}

/** Club score distribution per year (over the window when `range` is given); this feature sums the years for "distribution vs club" (Decision D11). */
export function useClubDistribution(range: WindowRange | null) {
  const [roundTypes] = useRoundTypes();
  const query = { by: 'year' as const, round_type: roundTypes, ...windowQuery(range) };
  return useQuery({
    queryKey: ['/api/club/distribution', query],
    queryFn: () => unwrap(api.GET('/api/club/distribution', { params: { query } })),
    enabled: range !== null,
  });
}

/** The club distribution over every year, for the fullscreen chart and the CSV. */
export function fetchAllClubDistribution(queryClient: QueryClient, roundTypes: RoundTypeValue[]) {
  const query = { by: 'year' as const, round_type: roundTypes };
  return queryClient.ensureQueryData({
    queryKey: ['/api/club/distribution', query],
    queryFn: () => unwrap(api.GET('/api/club/distribution', { params: { query } })),
  });
}
