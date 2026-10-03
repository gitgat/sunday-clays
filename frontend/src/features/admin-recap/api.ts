import { skipToken, useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import type { JsonOf } from '../admin/api';

export type Recap = JsonOf<paths['/api/admin/recap/{date}']['get']>;

export function useRecap(date: string | null) {
  return useQuery({
    queryKey: ['/api/admin/recap/{date}', date],
    queryFn:
      date === null
        ? skipToken
        : () => unwrap(api.GET('/api/admin/recap/{date}', { params: { path: { date } } })),
  });
}
