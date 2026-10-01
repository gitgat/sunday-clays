import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { PageKey } from '../../components/layout/pageTop';

/** The feed as the API client returns it (every insight route answers InsightFeedOut). */
export type InsightFeed = NonNullable<ReturnType<typeof useSundayFeed>['data']>;
export type Insight = InsightFeed['top'][number];
export type InsightSegment = Insight['headline'][number];
export type InsightChart = Insight['chart'];
export type InsightKudos = InsightFeed['kudos'][number];

/**
 * Insight feeds (Plan 12, spec §3.7). Read-only and keyed by `data_version` on the server
 * (ETag): the text never changes between recomputes, so a long stale time is safe. Every viewer
 * sees every feed, digest line included (D11); only the "you" wording depends on "That's me".
 */
const STALE = 5 * 60 * 1000;

/** `all` lifts the "More insights" cap (the server otherwise sends the first 30); the top cards stay on screen while it loads. */
export function useShooterFeed(id: number, all = false) {
  return useQuery({
    queryKey: ['/api/insights/shooters/{id}', id, { all }],
    queryFn: () =>
      unwrap(
        api.GET('/api/insights/shooters/{id}', {
          params: { path: { id }, query: all ? { all: true } : {} },
        }),
      ),
    placeholderData: (prev, prevQuery) => (prevQuery?.queryKey[1] === id ? prev : undefined),
    staleTime: STALE,
  });
}

export function useSundayFeed(date: string) {
  return useQuery({
    queryKey: ['/api/insights/sundays/{date}', date],
    queryFn: () => unwrap(api.GET('/api/insights/sundays/{date}', { params: { path: { date } } })),
    staleTime: STALE,
  });
}

/**
 * The club, leaderboards, records and stations feeds. `season` (leaderboards only) is the calendar
 * year of the points race the page shows; the server answers an empty feed for any year but the
 * latest Sunday's (v1).
 */
export function usePageFeed(page: PageKey, season: number | null = null) {
  return useQuery({
    queryKey: [`/api/insights/${page}`, season],
    queryFn: () => {
      switch (page) {
        case 'club':
          return unwrap(api.GET('/api/insights/club'));
        case 'leaderboards':
          return unwrap(
            api.GET('/api/insights/leaderboards', {
              params: { query: { season: season ?? undefined } },
            }),
          );
        case 'records':
          return unwrap(api.GET('/api/insights/records'));
        case 'stations':
          return unwrap(api.GET('/api/insights/stations'));
      }
    },
    staleTime: STALE,
  });
}
