import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import { useRoundTypes } from '../../lib/roundTypes';
import type { paths } from '../../api/schema';

type JsonOf<Op> = Op extends { responses: { 200: { content: { 'application/json': infer R } } } }
  ? R
  : never;

export type Meta = JsonOf<paths['/api/meta']['get']>;
export type EventSummary = JsonOf<paths['/api/events']['get']>[number];
export type EventDetail = JsonOf<paths['/api/events/{date}']['get']>;
export type ShooterDetail = JsonOf<paths['/api/shooters/{id}']['get']>;
export type ShooterRound = JsonOf<paths['/api/shooters/{id}/rounds']['get']>[number];

// Query keys equal the ones features/events and features/shooters use for the same requests, so
// the TanStack cache is shared at runtime (D2).

export function useMeta() {
  return useQuery({ queryKey: ['/api/meta'], queryFn: () => unwrap(api.GET('/api/meta')) });
}

/** `date === null` waits (no event is known yet). */
export function useEventDetail(date: string | null) {
  return useQuery({
    queryKey: ['/api/events/{date}', date],
    // Only runs while enabled, i.e. with a non-null date.
    queryFn: () =>
      unwrap(api.GET('/api/events/{date}', { params: { path: { date: String(date) } } })),
    enabled: date !== null,
  });
}

export { useWindowEvents, type WindowEvents } from '../../lib/windowEvents';

/** Detail + odometer for the remembered "me"; 404 when the id was merged away (Review Focus #2). */
export function useShooterDetail(id: number) {
  const [roundTypes] = useRoundTypes();
  return useQuery({
    queryKey: ['/api/shooters/{id}', id, { round_type: roundTypes }],
    queryFn: () =>
      unwrap(
        api.GET('/api/shooters/{id}', {
          params: { path: { id }, query: { round_type: roundTypes } },
        }),
      ),
  });
}

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
