import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query';
import { useState } from 'react';
import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type BumpState = components['schemas']['BumpStateOut'];
export type BumpCounts = Record<string, BumpState>;

/** The server's cap on keys per GET /api/bumps (api/routes/bumps.py MAX_KEYS). */
export const BATCH = 100;

export const BUMPS_OFF = 'Bumps need this browser to remember you';
export const BUMPS_UNAVAILABLE = 'Bump counts aren’t available right now';

/** Distinct keys in a stable order, so one set of insights is one query. */
export function sortedKeys(keys: Iterable<string>): string[] {
  return [...new Set(keys)].sort();
}

export function bumpsKey(keys: readonly string[], deviceId: string | null) {
  return ['/api/bumps', deviceId, keys] as const;
}
export type BumpsKey = ReturnType<typeof bumpsKey>;

/**
 * Which counts maps have had a successful load from the server. Our own optimistic writes never
 * count: only an answer that reached the client does (ruling P15-R2).
 */
const served = new WeakMap<QueryClient, Set<string>>();
const servedKey = (queryKey: BumpsKey) => JSON.stringify(queryKey);
function markServed(qc: QueryClient, queryKey: BumpsKey) {
  const keys = served.get(qc) ?? new Set<string>();
  keys.add(servedKey(queryKey));
  served.set(qc, keys);
}
function hasServed(qc: QueryClient, queryKey: BumpsKey) {
  return served.get(qc)?.has(servedKey(queryKey)) ?? false;
}

async function fetchCounts(keys: readonly string[], deviceId: string | null): Promise<BumpCounts> {
  const chunks: string[][] = [];
  for (let i = 0; i < keys.length; i += BATCH) chunks.push(keys.slice(i, i + BATCH));
  const device = deviceId === null ? {} : { device_id: deviceId };
  const parts = await Promise.all(
    chunks.map((chunk) =>
      unwrap(api.GET('/api/bumps', { params: { query: { keys: chunk.join(','), ...device } } })),
    ),
  );
  return parts.reduce<BumpCounts>((all, part) => ({ ...all, ...part }), {});
}

/**
 * Bump counts for one page section's insights: one request for up to BATCH keys, and more go
 * in parallel chunks. Never cached by the server, and refetched whenever a page mounts. While a
 * new set of keys loads (a profile's "Show all"), the previous counts stay on screen.
 */
export function useBumps(keys: readonly string[], deviceId: string | null) {
  const qc = useQueryClient();
  const queryKey = bumpsKey(keys, deviceId);
  return useQuery({
    queryKey,
    queryFn: async ({ signal }) => {
      const counts = await fetchCounts(keys, deviceId);
      // A fetch cancelled by a tap did not deliver its answer.
      if (!signal.aborted) markServed(qc, queryKey);
      return counts;
    },
    enabled: keys.length > 0,
    staleTime: 0,
    placeholderData: keepPreviousData,
  });
}

/** `old` with this device's bump on `key` set to `bump` (a no-op when it already is). */
export function toggled(old: BumpCounts | undefined, key: string, bump: boolean): BumpCounts {
  const current = old?.[key] ?? { bumps: 0, bumped: false };
  if (current.bumped === bump) return { ...old, [key]: current };
  return {
    ...old,
    [key]: { bumps: Math.max(0, current.bumps + (bump ? 1 : -1)), bumped: bump },
  };
}

/**
 * Bump or take back a bump on one insight. The count changes at once (optimistic). The request
 * runs after any earlier one for the same insight (one mutation scope per insight), so two quick
 * taps reach the server in order. A failure puts this insight's count back and sets `failed`.
 * Only the last request for an insight writes the server's answer, so an earlier answer never
 * undoes a newer tap.
 */
export function useBumpToggle(
  queryKey: BumpsKey,
  deviceId: string,
  insightKey: string,
  /** The counts on screen, including a keepPreviousData placeholder while a new key set loads. */
  shown?: BumpCounts,
) {
  const qc = useQueryClient();
  const [failed, setFailed] = useState(false);
  const mutationKey = ['bump', insightKey];
  const mutation = useMutation({
    mutationKey,
    scope: { id: `bump:${insightKey}` },
    mutationFn: ({
      bump,
    }: {
      bump: boolean;
      previous: BumpState | undefined;
      refetch: boolean;
    }) => {
      const body = { key: insightKey, device_id: deviceId };
      return bump
        ? unwrap(api.POST('/api/bumps', { body }))
        : unwrap(api.DELETE('/api/bumps', { body }));
    },
    onError: (_error, { previous }) => {
      // Only this insight goes back: a bump on another one may have succeeded meanwhile.
      qc.setQueryData<BumpCounts>(queryKey, (old) => ({
        ...old,
        [insightKey]: previous ?? { bumps: 0, bumped: false },
      }));
      setFailed(true);
    },
    onSuccess: (state) => {
      // This request still counts as pending here: 1 means no newer tap is queued behind it.
      if (qc.isMutating({ mutationKey }) <= 1) {
        qc.setQueryData<BumpCounts>(queryKey, (old) => ({ ...old, [insightKey]: state }));
      }
    },
    onSettled: (_data, _error, { refetch }) => {
      // The counts were not loaded when this was tapped, so the map holds only this insight: once
      // the last queued tap for it settles, fetch the whole map again.
      if (refetch && qc.isMutating({ mutationKey }) <= 1) {
        void qc.invalidateQueries({ queryKey });
      }
    },
  });
  function send(bump: boolean) {
    setFailed(false);
    const cached = qc.getQueryData<BumpCounts>(queryKey);
    // Has the server ever answered for this map? A tap's own optimistic write never counts.
    const loaded = hasServed(qc, queryKey);
    // While a new key set loads ("Show all"), this key's entry is empty but the section still shows
    // the previous counts (keepPreviousData). Seed from those, so no other card flashes to 0.
    const counts = cached ?? shown;
    // Read before any cancel: a fetch in flight now is one this tap may kill.
    const inFlight = qc.isFetching({ queryKey, exact: true }) > 0;
    // Once loaded, an ask still in flight is stale next to this tap: drop it. Before the first load
    // it is never cancelled (it is the only way the other cards get their counts).
    if (loaded) void qc.cancelQueries({ queryKey });
    qc.setQueryData<BumpCounts>(queryKey, toggled(counts, insightKey, bump));
    // Owed: a fetch after the last queued tap settles. Before the first load always; after it, only
    // when a fetch was cancelled above. A tap still queued for this insight hands its duty on.
    const owes = qc
      .getMutationCache()
      .findAll({ mutationKey, status: 'pending' })
      .some((m) => (m.state.variables as { refetch?: boolean } | undefined)?.refetch === true);
    mutation.mutate({
      bump,
      previous: counts?.[insightKey],
      refetch: !loaded || inFlight || owes,
    });
  }
  return { send, failed };
}
