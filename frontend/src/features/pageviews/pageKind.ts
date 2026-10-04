import type { components } from '../../api/schema';

export type PageKind = components['schemas']['PageViewIn']['page_kind'];

/** First path segment → kind, for pages whose deeper levels do not matter. */
const BY_SEGMENT = new Map<string, PageKind>([
  ['leaderboards', 'leaderboards'],
  ['records', 'records'],
  ['club', 'club'],
  ['stations', 'stations'],
  ['weather', 'weather'],
  ['yir', 'yir'],
  ['explorer', 'explorer'],
  ['achievements', 'achievements'],
  ['race', 'race'],
  ['compare', 'compare'],
  ['club-events', 'club-events'],
  ['admin', 'admin'],
]);

/**
 * The coarse category of a path (Plan 16). Never the URL and never an id: every profile is
 * "profile" and every Sunday's page is "event". The Shooters list is "other" (Decision 17).
 */
export function pageKind(pathname: string): PageKind {
  const [first, second] = pathname.split('/').filter(Boolean);
  if (first === undefined) return 'home';
  if (first === 'events') return second === undefined ? 'events-list' : 'event';
  if (first === 'shooters') return second === undefined ? 'other' : 'profile';
  return BY_SEGMENT.get(first) ?? 'other';
}
