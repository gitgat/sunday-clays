// The header time window as the stations endpoints take it (`since` / `as_of`), plus the plain
// words the stations pages use to name it.
import { useMemo } from 'react';
import {
  useMeta,
  useTimeWindow,
  windowPhrase,
  type TimeWindow,
  type WindowRange,
} from '../../lib/timeWindow';
import { windowTagText } from '../../lib/windowText';

type EraSel = 'current' | 'all';

export interface StationWindowQuery {
  since?: string;
  as_of?: string;
}

export interface StationWindow {
  window: TimeWindow;
  range: WindowRange | null;
  /** The dates to send. "All" sends none, so a station sheet after the latest score still counts. */
  query: StationWindowQuery;
  /** False until the latest scored Sunday is known, so no request goes out wider than its tag. */
  ready: boolean;
  /** The Sunday lookup failed, so the window can never be resolved. */
  failed: boolean;
  setWindow: (next: TimeWindow) => void;
}

export function useStationWindow(): StationWindow {
  const { window, range, setWindow } = useTimeWindow();
  const meta = useMeta();
  const query = useMemo<StationWindowQuery>(() => {
    // Not resolved yet, or "All" (no lower bound): no dates, so a sheet after the latest score counts.
    if (range === null || range.from === null) return {};
    return { since: range.from, as_of: range.to };
  }, [range]);
  return {
    window,
    range,
    query,
    // "All" needs no anchor, so it never waits for /api/meta.
    ready: window === 'all' || range !== null || meta.isSuccess,
    // "All" needs no anchor, so a failed lookup does not stop it.
    failed: window !== 'all' && range === null && meta.isError,
    setWindow,
  };
}

/** "in the last 8 weeks"; the whole history reads "so far". */
export function inPeriod(window: TimeWindow): string {
  return window === 'all' ? 'so far' : `in ${windowPhrase(window)}`;
}

/** "Current setups · Last 8 weeks · Aug 3 – Sep 27": what a page's numbers cover. */
export function scopeText(era: EraSel, window: TimeWindow, range: WindowRange | null): string {
  const setups = era === 'current' ? 'Current setups' : 'All setups';
  return `${setups} · ${windowTagText(window, range)}`;
}
