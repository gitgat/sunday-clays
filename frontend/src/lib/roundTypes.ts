import { useCallback, useMemo } from 'react';
import type { To } from 'react-router';
import { useExplicitWindow, windowCodec, type TimeWindow } from './timeWindowChoice';
import { enumCodec, listCodec, useUrlState, type Codec } from './useUrlState';

export const ROUND_TYPES = ['sporting', 'super_sporting'] as const;
export type RoundTypeValue = (typeof ROUND_TYPES)[number];

export const ROUND_TYPE_LABELS: Record<RoundTypeValue, string> = {
  sporting: 'Sporting',
  super_sporting: 'Super Sporting',
};

export const roundTypesCodec: Codec<RoundTypeValue[]> = listCodec(enumCodec(ROUND_TYPES));

const NONE: RoundTypeValue[] = [];

/**
 * The global round-type filter (C10), stored in the `rt` query parameter; [] = no filter.
 * Every round type selected filters nothing out, so a URL naming both reads as no filter too.
 */
export function useRoundTypes(): [RoundTypeValue[], (next: RoundTypeValue[]) => void] {
  const [value, setValue] = useUrlState('rt', roundTypesCodec, NONE);
  return [value.length === ROUND_TYPES.length ? NONE : value, setValue];
}

/**
 * The global query parameters in-app links carry, in the order they are written: `rt` (round
 * types) and `w` (time window), each only when the URL names it. Encoded exactly as the
 * hooks write them.
 */
function globalParams(rt: RoundTypeValue[], w: TimeWindow | null): [string, string][] {
  const params: [string, string][] = [];
  if (rt.length > 0) params.push(['rt', roundTypesCodec.serialize(rt)]);
  // Only a window the URL names travels (8W included); a page's own default never does.
  if (w !== null) params.push(['w', windowCodec.serialize(w)]);
  return params;
}

/**
 * A link target for `path` (a pathname, no query) that keeps the global round-type filter and time
 * window, so in-app navigation never silently drops them (spec §4). Encoded as the hooks write them.
 */
export function useRoundTypeLink(path: string): To {
  const [rt] = useRoundTypes();
  const w = useExplicitWindow();
  return useMemo(() => {
    const param = new URLSearchParams(globalParams(rt, w)).toString();
    return { pathname: path, search: param && `?${param}` };
  }, [path, rt, w]);
}

/**
 * `href` (an in-app path, with an optional query and hash) carrying the round-type filter `rt` and
 * the time window `w`, except a key the href names itself. The rest of the href is kept exactly as
 * written; a window is only added when given.
 */
export function withRoundTypes(
  href: string,
  rt: RoundTypeValue[],
  w: TimeWindow | null = null,
): string {
  const hashAt = href.indexOf('#');
  const hash = hashAt === -1 ? '' : href.slice(hashAt);
  const beforeHash = hashAt === -1 ? href : href.slice(0, hashAt);
  const queryAt = beforeHash.indexOf('?');
  const path = queryAt === -1 ? beforeHash : beforeHash.slice(0, queryAt);
  const query = queryAt === -1 ? '' : beforeHash.slice(queryAt + 1);
  const own = new URLSearchParams(query);
  const missing = globalParams(rt, w).filter(([key]) => !own.has(key));
  if (missing.length === 0) return href;
  const added = new URLSearchParams(missing).toString();
  return `${path}?${query === '' ? added : `${query}&${added}`}${hash}`;
}

/**
 * withRoundTypes bound to the current global filter and window, for hrefs built per row: every
 * drill link (a ChartFrame table row, a ChartCard chart click) goes through this, so drilling keeps
 * `rt` and `w` as the nav links do (C10: the filters are global).
 */
export function useRoundTypeHref(): (href: string) => string {
  const [rt] = useRoundTypes();
  const w = useExplicitWindow();
  return useCallback((href: string) => withRoundTypes(href, rt, w), [rt, w]);
}
