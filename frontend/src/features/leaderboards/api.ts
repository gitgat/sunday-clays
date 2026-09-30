import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import { useRoundTypes } from '../../lib/roundTypes';

type JsonOf<Op> = Op extends { responses: { 200: { content: { 'application/json': infer R } } } }
  ? R
  : never;

export type LeaderboardOut = JsonOf<paths['/api/leaderboards']['get']>;
export type LeaderboardRowOut = LeaderboardOut['rows'][number];
export type LeaderboardPeriod = LeaderboardOut['period'];
export type LeaderboardMetric = LeaderboardOut['metric'];
export type ShooterStatus = 'member' | 'guest' | 'deceased';

export interface LeaderboardQuery {
  /** With a start date the period is ignored by the API (a season keeps the request valid). */
  period: LeaderboardPeriod;
  metric: LeaderboardMetric;
  asOf: string | null;
  gauge: string | null;
  status: ShooterStatus | null;
  /** A start date (3M, 6M, Custom): the board covers [since, as_of] and the period is ignored. */
  since: string | null;
  /** False holds the request back (e.g. a start date after the end date). */
  enabled: boolean;
}

export function useLeaderboard({
  period,
  metric,
  asOf,
  gauge,
  status,
  since,
  enabled,
}: LeaderboardQuery) {
  const [roundTypes] = useRoundTypes();
  const query = {
    period,
    metric,
    as_of: asOf ?? undefined,
    since: since ?? undefined,
    gauge: gauge ?? undefined,
    status: status ?? undefined,
    round_type: roundTypes.length > 0 ? roundTypes : undefined,
  };
  return useQuery({
    queryKey: ['/api/leaderboards', query],
    queryFn: () => unwrap(api.GET('/api/leaderboards', { params: { query } })),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export type MoversOut = JsonOf<paths['/api/leaderboards/movers']['get']>;
export type ClimberOut = MoversOut['rows'][number];

export interface MoversQuery {
  period: LeaderboardPeriod;
  /** A start date (3M, 6M, Custom, or an insight's window): the period is then ignored. */
  since: string | null;
  asOf: string | null;
  /** The Members/Guests/In memoriam filter of the page. */
  status: ShooterStatus | null;
  /** False holds the request back until the window can be dated. */
  enabled: boolean;
}

/** The biggest rating gains over the header window (Plan 12 `lb-movers`); climbers only. */
export function useRatingMovers({ period, since, asOf, status, enabled }: MoversQuery) {
  const query = {
    period,
    since: since ?? undefined,
    as_of: asOf ?? undefined,
    status: status ?? undefined,
  };
  return useQuery({
    queryKey: ['/api/leaderboards/movers', query],
    queryFn: () => unwrap(api.GET('/api/leaderboards/movers', { params: { query } })),
    placeholderData: keepPreviousData,
    enabled,
  });
}
