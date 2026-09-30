import { useQuery } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import { useRoundTypes, type RoundTypeValue } from '../../lib/roundTypes';

type JsonOf<Op> = Op extends { responses: { 200: { content: { 'application/json': infer R } } } }
  ? R
  : never;

export type RecordsOut = JsonOf<paths['/api/records']['get']>;
export type RecordRoundOut = RecordsOut['highest_scores'][number];
export type RecordJumpOut = RecordsOut['biggest_jumps'][number];
export type RecordShooterOut = RecordsOut['most_events'][number];
export type RecordRatingOut = RecordsOut['highest_ratings'][number];

export interface RecordsQuery {
  /** First Sunday counted (inclusive); null = the beginning. */
  since: string | null;
  /** Last Sunday counted (inclusive); null = the latest scored Sunday. */
  asOf: string | null;
  /** False holds the request back (until the window's dates are known). */
  enabled?: boolean;
}

/** The most rows one list can hold (`limit` maximum); a longer list is asked for at this many. */
export const RECORDS_MAX_ROWS = 500;

/** The query `GET /api/records` is sent for these dates, round types and row limit (default 10). */
export function recordsQuery(
  roundTypes: readonly RoundTypeValue[],
  since: string | null,
  asOf: string | null,
  limit?: string,
) {
  return {
    round_type: roundTypes.length > 0 ? [...roundTypes] : undefined,
    since: since ?? undefined,
    as_of: asOf ?? undefined,
    limit,
  };
}

/** As many rows as the list has, up to the server's longest allowed list; never the uncapped `all`. */
export function expandedLimit(total: number): string {
  return String(Math.max(1, Math.min(total, RECORDS_MAX_ROWS)));
}

/** `limit` rows of every list (the page's own dates and filters), sized by `expandedLimit`. */
export function fetchAllRecords(
  roundTypes: readonly RoundTypeValue[],
  since: string | null,
  asOf: string | null,
  limit: string,
) {
  const query = recordsQuery(roundTypes, since, asOf, limit);
  return unwrap(api.GET('/api/records', { params: { query } }));
}

/**
 * C8 `GET /api/records`: club records over `[since, as_of]` (the header time window), following the
 * global round-type filter (C10). Ten rows a list, with each list's total.
 */
export function useRecords({ since, asOf, enabled = true }: RecordsQuery) {
  const [roundTypes] = useRoundTypes();
  const query = recordsQuery(roundTypes, since, asOf);
  return useQuery({
    queryKey: ['/api/records', query],
    queryFn: () => unwrap(api.GET('/api/records', { params: { query } })),
    enabled,
  });
}

/** Every row of every list, fetched only once a card asks for "Show all". */
export function useAllRecords(
  { since, asOf }: Pick<RecordsQuery, 'since' | 'asOf'>,
  limit: string,
  enabled: boolean,
) {
  const [roundTypes] = useRoundTypes();
  return useQuery({
    queryKey: ['/api/records', recordsQuery(roundTypes, since, asOf, limit), 'show-all'],
    queryFn: () => fetchAllRecords(roundTypes, since, asOf, limit),
    enabled,
  });
}
