import { keepPreviousData, skipToken, useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import { useRoundTypes } from '../../lib/roundTypes';
import { useStationWindow } from './window';

export type EraSel = 'current' | 'all';

// `useRoundTypes()` is Plan 07 T4's global filter (C10 `rt` param, parsed by `roundTypesCodec`,
// unknown values dropped). Its value goes into every request and every queryKey (C10).

// Every hook also sends the header time window (`since` / `as_of`) and keys on it, and waits until
// the window is resolved so a request never goes out wider than the tag on screen says.

export function useStations(era: EraSel) {
  const [roundTypes] = useRoundTypes();
  const { query, ready } = useStationWindow();
  return useQuery({
    queryKey: ['/api/stations', era, roundTypes, query],
    queryFn: ready
      ? () =>
          unwrap(
            api.GET('/api/stations', {
              params: { query: { era, round_type: roundTypes, ...query } },
            }),
          )
      : skipToken,
    // Switching era keeps the previous overview on screen instead of a loading flash.
    placeholderData: keepPreviousData,
  });
}

/** A station label such as "7" or "7A"; `null` (overview still loading) skips the request (TanStack v5 `skipToken`). */
export function useStation(label: string | null, era: EraSel) {
  const [roundTypes] = useRoundTypes();
  const { query, ready } = useStationWindow();
  return useQuery({
    queryKey: ['/api/stations/{label}', label, era, roundTypes, query],
    queryFn:
      label === null || !ready
        ? skipToken
        : () =>
            unwrap(
              api.GET('/api/stations/{label}', {
                params: { path: { label }, query: { era, round_type: roundTypes, ...query } },
              }),
            ),
    // An era switch keeps the same station on screen; a different station loads fresh.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === label ? previous : undefined,
  });
}

export function useShooterStations(shooterId: number, era: EraSel) {
  const [roundTypes] = useRoundTypes();
  const { query, ready } = useStationWindow();
  return useQuery({
    queryKey: ['/api/shooters/{id}/stations', shooterId, era, roundTypes, query],
    queryFn: ready
      ? () =>
          unwrap(
            api.GET('/api/shooters/{id}/stations', {
              params: {
                path: { id: shooterId },
                query: { era, round_type: roundTypes, ...query },
              },
            }),
          )
      : skipToken,
    placeholderData: keepPreviousData,
  });
}
