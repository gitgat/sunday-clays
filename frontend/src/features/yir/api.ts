import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { components, paths } from '../../api/schema';
import { useRoundTypes } from '../../lib/roundTypes';

type JsonOf<Op> = Op extends { responses: { 200: { content: { 'application/json': infer R } } } }
  ? R
  : never;

export type YirClub = components['schemas']['YirClubOut'];
export type YirShooter = components['schemas']['YirShooterOut'];
export type OnThisDay = components['schemas']['OnThisDayOut'];
export type OnThisDayItem = components['schemas']['OnThisDayItemOut'];
/** `GET /api/leaderboards` (rows carry rank, shooter_id, display_name, value). */
export type Leaderboard = JsonOf<paths['/api/leaderboards']['get']>;
/** The metric union, taken from the response as the leaderboards feature's own `api.ts` does. */
export type LeaderboardMetric = Leaderboard['metric'];

export function useYirClub(year: number) {
  const [roundTypes] = useRoundTypes();
  const query = { round_type: roundTypes.length > 0 ? roundTypes : undefined };
  return useQuery({
    queryKey: ['/api/yir/{year}', year, query],
    queryFn: () => unwrap(api.GET('/api/yir/{year}', { params: { path: { year }, query } })),
  });
}

export function useYirShooter(year: number, shooterId: number) {
  const [roundTypes] = useRoundTypes();
  const query = { round_type: roundTypes.length > 0 ? roundTypes : undefined };
  return useQuery({
    queryKey: ['/api/yir/{year}/shooters/{id}', year, shooterId, query],
    queryFn: () =>
      unwrap(
        api.GET('/api/yir/{year}/shooters/{id}', {
          params: { path: { year, id: shooterId }, query },
        }),
      ),
  });
}

export function useOnThisDay() {
  return useQuery({
    queryKey: ['/api/on-this-day'],
    queryFn: () => unwrap(api.GET('/api/on-this-day')),
  });
}

/**
 * A calendar-year board: the leaderboards' "this year" period (1 January to `asOf`, or to today when
 * `asOf` is undefined), filtered by the global round type. The key matches the leaderboards feature's.
 */
export function useYearBoard(metric: LeaderboardMetric, asOf: string | undefined) {
  const [roundTypes] = useRoundTypes();
  const query = {
    period: 'ytd' as const,
    metric,
    as_of: asOf,
    round_type: roundTypes.length > 0 ? roundTypes : undefined,
  };
  return useQuery({
    queryKey: ['/api/leaderboards', query],
    queryFn: () => unwrap(api.GET('/api/leaderboards', { params: { query } })),
  });
}
