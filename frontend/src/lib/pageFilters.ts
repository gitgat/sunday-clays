import { useMatches } from 'react-router';

/**
 * Which global filters a page honours. The filter bar (desktop content header, phone top bar) shows a
 * control only for a filter the page's data actually follows; a page that follows neither shows no bar.
 * The URL keeps a hidden filter's value (`rt`, `w`), so returning to a page that honours it restores it.
 */
export interface PageFilters {
  /** The round-type filter (`?rt=`): the page's queries send `round_type`. */
  roundType: boolean;
  /** The time window (`?w=`): the page's charts and stats follow it. */
  window: boolean;
}

export const NO_FILTERS: PageFilters = { roundType: false, window: false };
export const ROUND_TYPE_ONLY: PageFilters = { roundType: true, window: false };
export const BOTH_FILTERS: PageFilters = { roundType: true, window: true };

/** What a feature route puts in its `handle`. */
export interface RouteHandle {
  /** Renders outside the session guard and the app shell (the login page). */
  public?: boolean;
  filters: PageFilters;
}

/** The filters of the page being shown (its route's `handle.filters`); a route with none declares neither. */
export function usePageFilters(): PageFilters {
  const matches = useMatches();
  for (const match of matches.toReversed()) {
    const filters = (match.handle as Partial<RouteHandle> | undefined)?.filters;
    if (filters !== undefined) return filters;
  }
  return NO_FILTERS;
}
