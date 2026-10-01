import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import type { JsonOf } from '../admin/api';

export type DataIssue = JsonOf<paths['/api/admin/data-issues']['get']>[number];
export type AuditEntry = JsonOf<paths['/api/admin/audit']['get']>[number];
export type BumpedPost = JsonOf<paths['/api/admin/sheet/bumps']['get']>[number];

export function useDataIssues() {
  return useQuery({
    queryKey: ['/api/admin/data-issues'],
    queryFn: () => unwrap(api.GET('/api/admin/data-issues')),
  });
}

/** Creates an alias_name rule for an unmatched station name and enqueues a rebuild (Plan 04 T3). */
export function useAssignAlias() {
  const qc = useQueryClient();
  return useMutation({
    onSuccess: () => qc.invalidateQueries({ queryKey: ['/api/admin/audit'] }),
    mutationFn: ({ shooterId, nameKey }: { shooterId: number; nameKey: string }) =>
      unwrap(
        api.POST('/api/admin/shooters/{id}/aliases', {
          params: { path: { id: shooterId } },
          body: { name_key: nameKey },
        }),
      ),
  });
}

/** Entries per request of the audit log (the endpoint's default page). */
export const AUDIT_PAGE_SIZE = 200;

/** Newest first, AUDIT_PAGE_SIZE at a time; a short page is the end of the log. */
export function useAudit() {
  return useInfiniteQuery({
    queryKey: ['/api/admin/audit'],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET('/api/admin/audit', {
          params: { query: { limit: AUDIT_PAGE_SIZE, offset: pageParam } },
        }),
      ),
    getNextPageParam: (last, pages) =>
      last.length < AUDIT_PAGE_SIZE ? undefined : pages.length * AUDIT_PAGE_SIZE,
  });
}

export function useRecompute() {
  const qc = useQueryClient();
  return useMutation({
    onSuccess: () => qc.invalidateQueries({ queryKey: ['/api/admin/audit'] }),
    mutationFn: (body: { recalibrate: boolean }) =>
      unwrap(api.POST('/api/admin/recompute', { body })),
  });
}

/** Sunday Sheet posts with fist bumps, most recently bumped first (Plan 14). */
export function useBumpedPosts() {
  return useQuery({
    queryKey: ['/api/admin/sheet/bumps'],
    queryFn: () => unwrap(api.GET('/api/admin/sheet/bumps')),
  });
}

/** Wipes every bump on one post; the wipe is audited, so the audit log refreshes too. */
export function useWipeBumps() {
  const qc = useQueryClient();
  return useMutation({
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['/api/admin/sheet/bumps'] });
      await qc.invalidateQueries({ queryKey: ['/api/admin/audit'] });
    },
    mutationFn: (postKey: string) =>
      unwrap(
        api.DELETE('/api/admin/sheet/bumps/{post_key}', {
          params: { path: { post_key: postKey } },
        }),
      ),
  });
}
