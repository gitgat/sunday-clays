import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import { FEATURES_QUERY_KEY } from '../../lib/features';
import type { JsonOf } from '../admin/api';

export type FeatureSwitch = JsonOf<paths['/api/admin/features']['get']>[number];

export const SWITCHES_QUERY_KEY = ['/api/admin/features'] as const;

export function useFeatureSwitches() {
  return useQuery({
    queryKey: SWITCHES_QUERY_KEY,
    queryFn: () => unwrap(api.GET('/api/admin/features')),
  });
}

/** PUT one switch; on success both the admin list and the switch set are refetched. */
export function useSetFeatureSwitch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      unwrap(
        api.PUT('/api/admin/features/{key}', { params: { path: { key } }, body: { enabled } }),
      ),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: SWITCHES_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: FEATURES_QUERY_KEY }),
      ]);
    },
  });
}
