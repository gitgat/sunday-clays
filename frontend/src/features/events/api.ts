import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import { useRoundTypes } from '../../lib/roundTypes';
import { isoDateCodec } from '../../lib/useUrlState';

type JsonOf<Op> = Op extends { responses: { 200: { content: { 'application/json': infer R } } } }
  ? R
  : never;

export type Meta = JsonOf<paths['/api/meta']['get']>;
export type EventSummary = JsonOf<paths['/api/events']['get']>[number];
export type EventDetail = JsonOf<paths['/api/events/{date}']['get']>;
export type EventResult = EventDetail['results'][number];
export type EventWeather = NonNullable<EventDetail['weather']>;
export type StationMatrix = NonNullable<EventDetail['stations']>;
export type Notable = EventDetail['notables'][number];
export type VsPrev = NonNullable<EventDetail['vs_prev']>;

export function useMeta() {
  return useQuery({
    queryKey: ['/api/meta'],
    queryFn: () => unwrap(api.GET('/api/meta')),
  });
}

/** `year === null` waits (the season is not known yet). Appends the global round-type filter (C10). */
export function useEvents(year: number | null) {
  const [roundTypes] = useRoundTypes();
  return useQuery({
    queryKey: ['/api/events', { year, round_type: roundTypes }],
    queryFn: () =>
      // Only runs while enabled, i.e. with a non-null year.
      unwrap(
        api.GET('/api/events', {
          params: { query: { year: Number(year), round_type: roundTypes } },
        }),
      ),
    enabled: year !== null,
  });
}

/**
 * A year's Sundays under every round type, whatever the round-type filter says: it tells the
 * calendar which hidden Sundays are "Other round type" rather than absent. With no filter active
 * it is the same query (same key) as `useEvents`.
 */
export function useEventsAnyRoundType(year: number | null) {
  return useQuery({
    queryKey: ['/api/events', { year, round_type: [] }],
    queryFn: () => unwrap(api.GET('/api/events', { params: { query: { year: Number(year) } } })),
    enabled: year !== null,
  });
}

/** Every season's Sundays (the round-type filter applied), for the previous/next Sunday buttons. */
export function useAllSundays() {
  const [roundTypes] = useRoundTypes();
  return useQuery({
    queryKey: ['/api/events', { year: null, round_type: roundTypes }],
    queryFn: () =>
      unwrap(api.GET('/api/events', { params: { query: { round_type: roundTypes } } })),
  });
}

/**
 * C8 `/api/events/{date}`; the endpoint takes no round-type filter. 404 `event_not_found` for a date
 * with no event. A `date` that is not a real YYYY-MM-DD date (a crafted URL) is never requested.
 */
export function useEvent(date: string) {
  return useQuery({
    queryKey: ['/api/events/{date}', date],
    queryFn: () => unwrap(api.GET('/api/events/{date}', { params: { path: { date } } })),
    enabled: isoDateCodec.parse(date) !== null,
  });
}
