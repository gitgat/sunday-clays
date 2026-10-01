import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, unwrap } from '../../api/client';

/**
 * The issue as the API client returns it. Typed through the hooks, like the insight feeds, so an
 * issue's insights are the same type as `features/insights` `Insight`.
 */
export type SheetIssue = NonNullable<ReturnType<typeof useSheet>['data']>;
export type SheetPost = SheetIssue['posts'][number];
export type SheetPostType = SheetPost['type'];
export type SheetMoreGroup = SheetIssue['more'][number];
export type BumpCounts = NonNullable<ReturnType<typeof useBumps>['data']>;
export type BumpState = BumpCounts[string];

/** The newest issue (`GET /api/sheet/latest`), or a Sunday's (`YYYY-MM-DD`). */
export type IssueRef = 'latest' | (string & {});

/** The issue body changes only with data_version (server ETag), so it may stay fresh a while. */
const STALE = 5 * 60 * 1000;

export function useSheet(ref: IssueRef) {
  return useQuery({
    queryKey: ['/api/sheet', ref],
    queryFn: () =>
      ref === 'latest'
        ? unwrap(api.GET('/api/sheet/latest'))
        : unwrap(api.GET('/api/sheet/{date}', { params: { path: { date: ref } } })),
    staleTime: STALE,
  });
}

export function bumpsKey(date: string, deviceId: string | null) {
  return ['/api/sheet/{date}/bumps', date, deviceId] as const;
}

/** Bump counts for every post of an issue; never cached by the server (they change any time). */
export function useBumps(date: string, deviceId: string | null) {
  return useQuery({
    queryKey: bumpsKey(date, deviceId),
    queryFn: () =>
      unwrap(
        api.GET('/api/sheet/{date}/bumps', {
          params: { path: { date }, query: deviceId === null ? {} : { device_id: deviceId } },
        }),
      ),
  });
}

/** `old` with this device's bump on `postKey` set to `bump` (a no-op when it already is). */
export function toggled(old: BumpCounts | undefined, postKey: string, bump: boolean): BumpCounts {
  const current = old?.[postKey] ?? { bumps: 0, bumped: false };
  if (current.bumped === bump) return { ...old, [postKey]: current };
  return {
    ...old,
    [postKey]: { bumps: Math.max(0, current.bumps + (bump ? 1 : -1)), bumped: bump },
  };
}

/**
 * Bump or take back a bump on one post. The count changes at once (optimistic); the request runs
 * after any earlier one for the same post (one mutation scope per post), so two quick taps reach
 * the server in order. A failure puts this post's count back and sets `failed`; only the last request
 * for a post writes the server's answer, so an earlier answer never undoes a newer tap.
 */
export function useBumpToggle(date: string, deviceId: string, postKey: string) {
  const qc = useQueryClient();
  const [failed, setFailed] = useState(false);
  const key = bumpsKey(date, deviceId);
  const mutationKey = ['bump', date, postKey];
  const mutation = useMutation({
    mutationKey,
    scope: { id: `bump:${date}:${postKey}` },
    mutationFn: ({ bump }: { bump: boolean; previous: BumpState | undefined }) => {
      const body = { post_key: postKey, device_id: deviceId };
      return bump
        ? unwrap(api.POST('/api/sheet/bumps', { body }))
        : unwrap(api.DELETE('/api/sheet/bumps', { body }));
    },
    onError: (_error, { previous }) => {
      // Only this post goes back: a bump on another post may have succeeded meanwhile.
      qc.setQueryData<BumpCounts>(key, (old) => ({
        ...old,
        [postKey]: previous ?? { bumps: 0, bumped: false },
      }));
      setFailed(true);
    },
    onSuccess: (state) => {
      // This request still counts as pending here: 1 means no newer tap is queued behind it.
      if (qc.isMutating({ mutationKey }) <= 1) {
        qc.setQueryData<BumpCounts>(key, (old) => ({ ...old, [postKey]: state }));
      }
    },
  });
  function send(bump: boolean) {
    setFailed(false);
    const counts = qc.getQueryData<BumpCounts>(key);
    void qc.cancelQueries({ queryKey: key });
    qc.setQueryData<BumpCounts>(key, toggled(counts, postKey, bump));
    mutation.mutate({ bump, previous: counts?.[postKey] });
  }
  return { send, failed };
}
