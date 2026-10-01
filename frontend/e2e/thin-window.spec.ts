import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import { thinCount } from './thinCount';
import { expectNoSideScroll, expectTapTargets, whenSettled } from './layout';

/** Every expectation comes from the API at run time: no wall clock, no hard-coded dates. */

interface Meta {
  last_score_date: string;
}

async function scoredSundaysInLast8Weeks(page: Page): Promise<number> {
  const meta = (await (await page.request.get('/api/meta')).json()) as Meta;
  const from = new Date(`${meta.last_score_date}T12:00:00Z`);
  from.setUTCDate(from.getUTCDate() - 55);
  const events = (await (
    await page.request.get(
      `/api/events?from=${from.toISOString().slice(0, 10)}&to=${meta.last_score_date}`,
    )
  ).json()) as { has_scores: boolean }[];
  return events.filter((e) => e.has_scores).length;
}

test('Club Turnout vs weather names a thin window and widens it in one tap', async ({ page }) => {
  const n = await scoredSundaysInLast8Weeks(page);
  await page.goto('/club');
  const card = page.getByRole('region', { name: 'Turnout vs weather', exact: true });
  await expect(card).toBeVisible({ timeout: 15_000 });
  const nudge = page.getByRole('note').filter({ hasText: 'Weather patterns need more' });
  if (n < 12) {
    await expect(nudge).toContainText(`${thinCount(n)} in the last 8 weeks.`);
    await whenSettled(page);
    await expectNoSideScroll(page);
    await expectTapTargets(page);
    await nudge.getByRole('button', { name: 'Show all time' }).click();
    await expect(page).toHaveURL(/w=all/);
  } else {
    await expect(nudge).toHaveCount(0);
  }
});

test('the Sheet asks for its club pulse in one request, for its own 8 weeks even at All time', async ({
  page,
}) => {
  const meta = (await (await page.request.get('/api/meta')).json()) as Meta;
  const from = new Date(`${meta.last_score_date}T12:00:00Z`);
  from.setUTCDate(from.getUTCDate() - 55);
  const eventRequests: string[] = [];
  page.on('request', (r) => {
    if (new URL(r.url()).pathname === '/api/events') eventRequests.push(r.url());
  });
  await page.goto('/?w=all');
  await expect(page.getByRole('region', { name: 'Turnout per Sunday' })).toBeVisible({
    timeout: 15_000,
  });
  await whenSettled(page);
  const pulse = eventRequests.filter((url) => !new URL(url).searchParams.has('year'));
  expect(pulse).toHaveLength(1);
  const query = new URL(pulse[0] ?? '').searchParams;
  expect(query.get('from')).toBe(from.toISOString().slice(0, 10));
  expect(query.get('to')).toBe(meta.last_score_date);
  expect(eventRequests.filter((url) => new URL(url).searchParams.has('year'))).toEqual([]);
  await expectNoSideScroll(page);
});
