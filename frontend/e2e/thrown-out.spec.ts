import { THROWN_OUT_COUNTS, THROWN_OUT_ROUNDS } from '../src/components/charts/thrownOutCopy';
import { thrownOutPhrase, type ThrownOut } from '../src/features/events/thrownOut';

import { expect, test } from './fixtures';

const DAY = '2026-09-06';

interface Detail {
  stats_excluded: boolean;
  thrown_out: ThrownOut[];
  stations: { layout: { label: string; dropped: boolean }[] } | null;
  results: { shooter_id: number }[];
}

interface Records {
  highest_scores: unknown[];
  totals: Record<string, number>;
}

test('the API marks the Sunday and its station', async ({ request }) => {
  const detail = (await (await request.get(`/api/events/${DAY}`)).json()) as Detail;
  expect(detail.stats_excluded).toBe(true);
  expect(detail.thrown_out).toEqual([{ station_label: '9', target_count: 7, credited: false }]);
  expect(detail.stations?.layout.find((s) => s.label === '9')?.dropped).toBe(true);
  const records = (await (
    await request.get(`/api/records?since=${DAY}&as_of=${DAY}`)
  ).json()) as Records;
  expect(records.highest_scores).toEqual([]);
  expect(records.totals.most_events).toBe(new Set(detail.results.map((r) => r.shooter_id)).size);
});

test('the Sunday page shows the banner, the * and the counts line', async ({ page, request }) => {
  const detail = (await (await request.get(`/api/events/${DAY}`)).json()) as Detail;
  const phrase = thrownOutPhrase(detail.thrown_out);
  expect(phrase).toBe('Station 9 was thrown out');
  await page.goto(`/events/${DAY}`);
  await expect(page.getByRole('note').filter({ hasText: phrase })).toBeVisible();
  await expect(page.getByRole('table', { name: 'Results' }).getByTitle(phrase)).toHaveCount(
    detail.results.length,
  );
  await page.getByRole('button', { name: 'About these results' }).click();
  await expect(page.getByText(THROWN_OUT_COUNTS)).toBeVisible();
});

test('a score board says thrown-out Sundays are left out, a points board says they count', async ({
  page,
}) => {
  for (const [metric, line] of [
    ['avg_score', THROWN_OUT_ROUNDS],
    ['season_points', THROWN_OUT_COUNTS],
  ] as const) {
    await page.goto(`/leaderboards?metric=${metric}`);
    const chart = page.getByRole('region', { name: /^Top \d+ · / });
    await chart.getByRole('button', { name: 'About this chart' }).click();
    await expect(chart.getByText(line)).toBeVisible();
  }
});
