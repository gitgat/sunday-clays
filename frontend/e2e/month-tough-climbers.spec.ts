import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import { expectNoSideScroll } from './layout';

const CHARTS = { timeout: 20_000 };

interface Listed {
  shooter_id: number;
  status: string;
  n_rounds: number;
}

async function busiestShooter(page: Page): Promise<number> {
  const listed = await page.request.get('/api/shooters');
  expect(listed.status()).toBe(200);
  const living = ((await listed.json()) as Listed[]).filter((s) => s.status !== 'deceased');
  return living.reduce((a, b) => (b.n_rounds > a.n_rounds ? b : a)).shooter_id;
}

test('Biggest rating gains lists the climbers the API names, with no ranks or places', async ({
  page,
}) => {
  const api = await page.request.get('/api/leaderboards/movers?period=all_time');
  expect(api.status()).toBe(200);
  const body = (await api.json()) as { rows: { display_name: string; gain: number }[] };
  expect(body.rows.length).toBeGreaterThan(0);
  expect(body.rows.every((r) => r.gain > 0)).toBe(true);
  await page.goto('/leaderboards?w=all');
  const region = page.getByRole('region', { name: 'Biggest rating gains', exact: true });
  await expect(region).toBeVisible(CHARTS);
  await expect(region.getByRole('button', { name: 'CSV' })).toBeVisible(CHARTS);
  await region.getByRole('button', { name: 'About this chart' }).click();
  await expect(region.getByRole('heading', { name: "How it's worked out" })).toBeVisible();
  await region.getByRole('button', { name: 'Table' }).click();
  const table = region.getByRole('table');
  await expect(table.getByRole('row').nth(1)).toContainText(body.rows[0]?.display_name ?? '');
  await expect(table.getByRole('columnheader', { name: /rank|place/i })).toHaveCount(0);
  await expectNoSideScroll(page);
});

test('the profile shows Tough days and the calendar by month, without sideways scroll', async ({
  page,
}) => {
  const id = await busiestShooter(page);
  await page.goto(`/shooters/${id}?w=all`);
  const tough = page.getByRole('region', { name: 'Tough days', exact: true });
  await expect(tough).toBeVisible(CHARTS);
  await expect(tough.getByRole('button', { name: 'CSV' })).toBeVisible(CHARTS);
  await tough.getByRole('button', { name: 'About this chart' }).click();
  await expect(tough.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  const calendar = page.getByRole('region', { name: /^Attendance calendar \d{4}$/ });
  await expect(calendar).toBeVisible(CHARTS);
  await calendar.getByRole('button', { name: 'By month', exact: true }).click();
  const months = page.getByRole('region', { name: 'Sundays shot per month', exact: true });
  await expect(months).toBeVisible(CHARTS);
  await expect(page).toHaveURL(/cal\.view=month/);
  await expect(months.getByRole('button', { name: 'CSV' })).toBeVisible(CHARTS);
  await months.getByRole('button', { name: 'By year', exact: true }).click();
  await expect(page.getByRole('region', { name: /^Attendance calendar \d{4}$/ })).toBeVisible(
    CHARTS,
  );
  await expectNoSideScroll(page);
});
