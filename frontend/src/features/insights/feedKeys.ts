import type { InsightFeed } from './api';

/** Every insight key a feed can put on screen, in feed order (BumpsProvider dedupes and sorts). */
export function feedKeys(feed: InsightFeed): string[] {
  const rows = [
    feed.pinned,
    feed.hero,
    feed.spotlight,
    feed.conditions,
    ...feed.top,
    ...feed.kudos.map((chip) => chip.insight),
    ...feed.more,
  ];
  return rows.flatMap((row) => (row == null ? [] : [row.key]));
}
