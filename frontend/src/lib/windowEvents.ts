import { skipToken, useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../api/client';
import type { paths } from '../api/schema';
import { useRoundTypes } from './roundTypes';
import { useMeta, useTimeWindow, type WindowRange } from './timeWindow';

export type WindowEvent =
  paths['/api/events']['get']['responses'][200]['content']['application/json'][number];

export interface WindowEvents {
  /** The active time window, anchored at the latest scored Sunday; null when nothing is scored. */
  range: WindowRange | null;
  /** Every Sunday inside the window (round-type filter applied), oldest first. */
  events: WindowEvent[];
  /** Scored Sundays inside the window: the number a "thin window" nudge counts. */
  sundays: number;
  isPending: boolean;
  error: Error | null;
}

/**
 * The Sundays inside the time window in ONE request (`GET /api/events?from&to`), however many
 * calendar years it spans: "All" used to cost a request per year.
 */
export function useWindowEvents(): WindowEvents {
  const { range } = useTimeWindow();
  const meta = useMeta();
  const [roundTypes] = useRoundTypes();
  const query = useQuery({
    queryKey: [
      '/api/events',
      { from: range?.from ?? null, to: range?.to ?? null, round_type: roundTypes },
    ],
    // Nothing scored yet (no anchor): nothing to ask for.
    queryFn:
      range === null
        ? skipToken
        : () =>
            unwrap(
              api.GET('/api/events', {
                params: {
                  query: {
                    round_type: roundTypes,
                    ...(range.from === null ? {} : { from: range.from }),
                    to: range.to,
                  },
                },
              }),
            ),
  });
  const events = query.data ?? [];
  return {
    range,
    events,
    sundays: events.filter((e) => e.has_scores).length,
    isPending: meta.isPending || (range !== null && query.isPending),
    error: query.error ?? meta.error,
  };
}
