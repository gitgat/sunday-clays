import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import type { WindowRange } from '../../lib/timeWindow';
import type { JsonOf } from '../admin/api';

export type ShooterSummary = JsonOf<paths['/api/shooters/{id}/summary']['get']>;

/** The card's numbers for the header window; `from` is left out for an open start ("All"). */
export function useShooterSummary(id: number, range: WindowRange | null, enabled: boolean) {
  const query =
    range === null ? null : { ...(range.from === null ? {} : { from: range.from }), to: range.to };
  return useQuery({
    queryKey: ['/api/shooters/{id}/summary', id, query],
    queryFn: () =>
      unwrap(
        api.GET('/api/shooters/{id}/summary', {
          params: { path: { id }, query: query as { from?: string; to: string } },
        }),
      ),
    enabled: enabled && query !== null,
  });
}
