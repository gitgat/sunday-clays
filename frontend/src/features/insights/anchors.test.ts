import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * Every chart an insight can link to (the backend's anchor registry, exported to a golden file by
 * tests/unit/analytics/insights/test_anchor_export.py) must exist on the page: a ChartFrame with
 * that `urlKey` (its card gets `id="chart-{urlKey}"`) or a card with that id. Read from disk: the
 * golden belongs to the backend.
 */
const anchors = JSON.parse(
  readFileSync(
    join(import.meta.dirname, '../../../../backend/tests/golden/insight_anchors.json'),
    'utf8',
  ),
) as Record<string, { route: string; urlKey: string }>;

const sources = import.meta.glob<string>(['../**/*.tsx', '!../**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

function declared(urlKey: string): boolean {
  const patterns = [`urlKey="${urlKey}"`, `id="chart-${urlKey}"`, `useChartTarget('${urlKey}')`];
  return Object.values(sources).some((text) => patterns.some((p) => text.includes(p)));
}

describe('insight chart anchors', () => {
  it('reads the backend anchor registry', () => {
    expect(Object.keys(anchors).length).toBeGreaterThanOrEqual(16);
  });

  it.each(Object.values(anchors).map((a) => [a.urlKey, a.route]))(
    '%s on %s is a chart or card on the page',
    (urlKey) => {
      expect(declared(urlKey), urlKey).toBe(true);
    },
  );
});
