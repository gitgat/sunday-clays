import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { api, unwrap } from '../api/client';
import {
  isCustomWindow,
  useWindowChoice,
  windowLabel,
  windowRange,
  type TimeWindow,
  type WindowRange,
} from './timeWindowChoice';

export * from './timeWindowChoice';

export interface TimeWindowState {
  window: TimeWindow;
  setWindow: (next: TimeWindow) => void;
  /** null until the anchor (GET /api/meta last_score_date) is known, or when nothing is scored. */
  range: WindowRange | null;
  label: string;
  /** True once `range` can be used. */
  ready: boolean;
}

/** GET /api/meta, shared by everything that needs the first or latest Sunday (one query key). */
export function useMeta() {
  return useQuery({
    queryKey: ['/api/meta'],
    queryFn: () => unwrap(api.GET('/api/meta')),
  });
}

/** The latest scored Sunday; null until /api/meta answers, or when nothing is scored. */
export function useLastScoreDate(): string | null {
  return useMeta().data?.last_score_date ?? null;
}

/** The global time window (`?w=`, default last 8 weeks), anchored at the latest scored Sunday. */
export function useTimeWindow(): TimeWindowState {
  const [window, setWindow] = useWindowChoice();
  const anchor = useLastScoreDate();
  // A custom window carries its own dates, so it needs neither /api/meta nor a scored Sunday.
  const range = useMemo(
    () =>
      isCustomWindow(window)
        ? windowRange(window, '')
        : anchor === null
          ? null
          : windowRange(window, anchor),
    [window, anchor],
  );
  return { window, setWindow, range, label: windowLabel(window), ready: range !== null };
}
