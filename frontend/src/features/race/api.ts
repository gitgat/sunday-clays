import { useQuery } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import { useRoundTypes, type RoundTypeValue } from '../../lib/roundTypes';

type JsonOf<Op> = Op extends { responses: { 200: { content: { 'application/json': infer R } } } }
  ? R
  : never;

export type LeaderboardHistoryOut = JsonOf<paths['/api/leaderboards/history']['get']>;
export type HistoryFrame = LeaderboardHistoryOut['frames'][number];
export type LeaderboardPeriod = LeaderboardHistoryOut['period'];
export type LeaderboardMetric = LeaderboardHistoryOut['metric'];

export interface RaceQuery {
  period: LeaderboardPeriod;
  metric: LeaderboardMetric;
  /** First and last Sunday replayed (inclusive). */
  from: string;
  to: string;
  top: number;
  /** False holds the request back until the dates are known and valid. */
  enabled: boolean;
}

/** The dates, points rule and measure of a race (everything but how many shooters each frame holds). */
export type RaceParams = Pick<RaceQuery, 'period' | 'metric' | 'from' | 'to'>;

/** The query `GET /api/leaderboards/history` is sent (the page and the fullscreen fetch share its shape). */
export function historyQuery(
  roundTypes: readonly RoundTypeValue[],
  { period, metric, from, to }: RaceParams,
  top: number,
) {
  return {
    period,
    metric,
    top,
    from,
    to,
    round_type: roundTypes.length > 0 ? [...roundTypes] : undefined,
  };
}

export type HistoryQueryParams = ReturnType<typeof historyQuery>;

export function fetchHistory(query: HistoryQueryParams) {
  return unwrap(api.GET('/api/leaderboards/history', { params: { query } }));
}

export function useLeaderboardHistory({ top, enabled, ...params }: RaceQuery) {
  const [roundTypes] = useRoundTypes();
  const query = historyQuery(roundTypes, params, top);
  return useQuery({
    queryKey: ['/api/leaderboards/history', query],
    queryFn: () => fetchHistory(query),
    enabled,
  });
}
