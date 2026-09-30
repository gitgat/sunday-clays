import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import type { JsonOf } from '../admin/api';
import type { RuleType } from './rules';

export type DuplicatePair = JsonOf<paths['/api/admin/possible-duplicates']['get']>[number];
export type ShooterRef = DuplicatePair['a'];
export type Rule = JsonOf<paths['/api/admin/rules']['get']>[number];
export type EventDetail = JsonOf<paths['/api/events/{date}']['get']>;
export type EventResult = EventDetail['results'][number];

export function usePossibleDuplicates() {
  return useQuery({
    queryKey: ['/api/admin/possible-duplicates'],
    queryFn: () => unwrap(api.GET('/api/admin/possible-duplicates')),
  });
}

/** Refetches the lists an identity change can alter (the rule it creates, and the duplicate names it renames or merges). */
export function useRefreshIdentity() {
  const qc = useQueryClient();
  return useCallback(() => {
    void qc.invalidateQueries({ queryKey: ['/api/admin/possible-duplicates'] });
    void qc.invalidateQueries({ queryKey: ['/api/admin/rules'] });
  }, [qc]);
}

export function useMergeShooters() {
  return useMutation({
    mutationFn: (body: {
      source_shooter_id: number;
      target_shooter_id: number;
      dry_run: boolean;
    }) => unwrap(api.POST('/api/admin/shooters/merge', { body })),
  });
}

export function useRenameShooter() {
  return useMutation({
    mutationFn: ({ id, displayName }: { id: number; displayName: string }) =>
      unwrap(
        api.POST('/api/admin/shooters/{id}/rename', {
          params: { path: { id } },
          body: { display_name: displayName },
        }),
      ),
  });
}

export function useSetStatus() {
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: 'member' | 'guest' | 'deceased' }) =>
      unwrap(
        api.POST('/api/admin/shooters/{id}/status', { params: { path: { id } }, body: { status } }),
      ),
  });
}

export function useRules() {
  return useQuery({
    queryKey: ['/api/admin/rules'],
    queryFn: () => unwrap(api.GET('/api/admin/rules')),
  });
}

export function useCreateRule() {
  return useMutation({
    mutationFn: (body: {
      rule_type: RuleType;
      payload: Record<string, string | number>;
      note: string | null;
    }) => unwrap(api.POST('/api/admin/rules', { body })),
  });
}

export function useDeactivateRule() {
  return useMutation({
    mutationFn: (id: number) =>
      unwrap(api.POST('/api/admin/rules/{id}/deactivate', { params: { path: { id } } })),
  });
}

/** Event results for the round picker; waits for a complete ISO date. Key matches features/events. */
export function useEventResults(date: string) {
  return useQuery({
    queryKey: ['/api/events/{date}', date],
    queryFn: () => unwrap(api.GET('/api/events/{date}', { params: { path: { date } } })),
    enabled: /^\d{4}-\d{2}-\d{2}$/.test(date),
  });
}
