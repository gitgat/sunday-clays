import { readFile } from 'node:fs/promises';

import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import { expectNoSideScroll, expectTapTargets, expectTitlesUntruncated } from './layout';
import { chooseWindow, datesText, daysBack, longDate, monthsBack } from './window';

/** The latest scored Sunday, from the API (never the wall clock). */
async function latestSunday(page: Page): Promise<string> {
  const response = await page.request.get('/api/meta');
  expect(response.ok()).toBe(true);
  const { last_score_date: last } = (await response.json()) as { last_score_date: string | null };
  if (last === null) throw new Error('the fixtures have scored Sundays');
  return last;
}

interface Frame {
  event_date: string;
  rows: { display_name: string; value: number }[];
}

async function frames(page: Page, query: string): Promise<Frame[]> {
  const response = await page.request.get(`/api/leaderboards/history?${query}`);
  expect(response.ok()).toBe(true);
  return ((await response.json()) as { frames: Frame[] }).frames;
}

test('the race opens on 12 months of Sundays with a plain intro, at any width', async ({
  page,
}) => {
  const latest = await latestSunday(page);
  const from = monthsBack(latest, 12);
  const api = await frames(
    page,
    `period=rolling_12&metric=season_points&top=10&from=${from}&to=${latest}`,
  );
  const last = api.at(-1);
  if (last === undefined) throw new Error('the fixtures have a Sunday in the last year');
  await page.goto('/race');
  await expect(page.getByRole('heading', { level: 1, name: 'Race' })).toBeVisible();
  const intro = page.getByRole('region', { name: 'About the race' });
  await expect(intro).toBeVisible();
  await expect(intro).toContainText('1st place earns 10, 2nd 8');
  await expect(intro).toContainText('last 52 Sundays');
  await expect(intro).toContainText('there is no reset');
  await expect(page.getByRole('button', { name: 'Last 12 months' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  // 12M is Race's page default: it shows in the header and is never written to the URL.
  await expect(page).not.toHaveURL(/[?&](w|period)=/);
  await expect(page.locator('output')).toHaveText(longDate(last.event_date));
  await expect(
    page.getByText(`Replaying ${datesText(from, latest, latest)} · ${String(api.length)} Sundays`),
  ).toBeVisible();
  await expectNoSideScroll(page);
  await expectTapTargets(page);
  await expectTitlesUntruncated(page);
});

test('the race has no date controls of its own, and the header window sets the Sundays', async ({
  page,
}) => {
  const latest = await latestSunday(page);
  await page.goto('/race');
  await expect(page.getByRole('list', { name: 'Standings' })).toBeVisible();
  await expect(page.getByLabel('Start date')).toHaveCount(0);
  await expect(page.getByLabel('End date')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Custom dates' })).toHaveCount(0);

  const from = daysBack(latest, 55);
  const api = await frames(
    page,
    `period=rolling_12&metric=season_points&top=10&from=${from}&to=${latest}`,
  );
  await chooseWindow(page, '8w');
  await expect(page).toHaveURL(/[?&]w=8w(&|$)/);
  await expect(
    page.getByText(`Replaying ${datesText(from, latest, latest)} · ${String(api.length)} Sunday`),
  ).toBeVisible();
  // Back to 12M: the page default, so the URL loses w again.
  await chooseWindow(page, '12m');
  await expect(page).not.toHaveURL(/[?&]w=/);
});

test('the year to date window ends on the latest Sunday with the API points leader', async ({
  page,
}) => {
  const anchor = await latestSunday(page);
  const api = await frames(
    page,
    `period=rolling_12&metric=season_points&top=10&from=${anchor.slice(0, 4)}-01-01&to=${anchor}`,
  );
  const last = api.at(-1);
  if (last === undefined) throw new Error('the fixtures have a Sunday this year');
  await page.goto('/race?w=ytd');
  await expect(page.locator('output').filter({ hasText: longDate(last.event_date) })).toBeVisible();
  await expect(
    page.getByRole('list', { name: 'Standings' }).getByRole('listitem').first(),
  ).toContainText(String(last.rows[0]?.value));
  await expect(page.getByRole('button', { name: /csv/i }).first()).toBeVisible();
});

test('play restarts the race from its first Sunday', async ({ page }) => {
  const anchor = await latestSunday(page);
  const api = await frames(
    page,
    `period=rolling_12&metric=season_points&top=10&from=${anchor.slice(0, 4)}-01-01&to=${anchor}`,
  );
  const first = api[0];
  if (first === undefined) throw new Error('the fixtures have a Sunday this year');
  await page.goto('/race?w=ytd');
  await page.getByRole('button', { name: 'Play' }).click();
  await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible();
  await expect(
    page.locator('output').filter({ hasText: longDate(first.event_date) }),
  ).toBeVisible();
});

test('the race matches the API frames, scrubs between them and never overflows sideways', async ({
  page,
}) => {
  const anchor = await latestSunday(page);
  const api = await frames(
    page,
    `period=rolling_12&metric=season_points&top=10&from=${anchor.slice(0, 4)}-01-01&to=${anchor}`,
  );
  const first = api[0];
  const last = api.at(-1);
  if (first === undefined || last === undefined)
    throw new Error('the fixtures have Sundays this year');

  await page.goto('/race?w=ytd');
  const date = page.locator('output');
  await expect(date).toHaveText(longDate(last.event_date));
  const standings = page.getByRole('list', { name: 'Standings' }).getByRole('listitem');
  await expect(standings).toHaveCount(last.rows.length);
  await expect(standings.first()).toContainText(String(last.rows[0]?.value));

  await page.getByLabel('Race position').fill('0');
  await expect(date).toHaveText(longDate(first.event_date));
  await expect(standings.first()).toContainText(first.rows[0]?.display_name ?? '');
  await expect(standings.first()).toContainText(String(first.rows[0]?.value));

  for (const chart of [
    page.getByRole('region', { name: 'Points', exact: true }),
    page.getByRole('region', { name: 'Rank over time' }),
  ]) {
    await chart.getByRole('button', { name: 'About this chart' }).click();
    await expect(chart.getByRole('heading', { name: 'What this shows' })).toBeVisible();
    await expect(chart.getByText(/^This year to date · /).first()).toBeVisible();
  }
  await expect(page.getByRole('button', { name: 'CSV' })).toHaveCount(2);
  await expect(page.getByRole('button', { name: 'Table' })).toHaveCount(2);
  await expectNoSideScroll(page);
});

test('the points rule: last 12 months is the default, and each choice asks the API for it', async ({
  page,
}) => {
  await page.goto('/race');
  const group = page.getByRole('group', { name: 'Points over' });
  await expect(group.getByRole('button')).toHaveText([
    'Last 12 months',
    'Last 8 Sundays',
    'Since Jan 1',
  ]);
  for (const [label, period] of [
    ['Last 8 Sundays', 'season'],
    ['Since Jan 1', 'ytd'],
  ] as const) {
    const api = page.waitForResponse(
      (r) => r.url().includes('/api/leaderboards/history') && r.url().includes(`period=${period}`),
    );
    await group.getByRole('button', { name: label }).click();
    expect((await api).ok()).toBe(true);
    await expect(group.getByRole('button', { name: label })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await expect(page).toHaveURL(new RegExp(`[?&]period=${period}(&|$)`));
  }
  await group.getByRole('button', { name: 'Last 12 months' }).click();
  await expect(page).not.toHaveURL(/period=/);
});

test('old Race links convert once into the window and replay exactly the API frames', async ({
  page,
}) => {
  const latest = await latestSunday(page);
  const from = daysBack(latest, 70);
  const to = daysBack(latest, 14);
  const api = await frames(
    page,
    `period=rolling_12&metric=season_points&top=10&from=${from}&to=${to}`,
  );
  await page.goto(`/race?since=${from}&until=${to}`);
  await expect(page).toHaveURL(new RegExp(`[?&]w=${from}\\.\\.${to}(&|$)`));
  await expect(page).not.toHaveURL(/since=|until=/);
  const slider = page.getByLabel('Race position');
  await expect(slider).toBeVisible();
  expect(Number(await slider.getAttribute('max')) + 1).toBe(api.length);
  await expectNoSideScroll(page);
});

test('a window with no Sundays says so in plain words and widens to 12M in one tap', async ({
  page,
}) => {
  await page.goto('/race?w=2000-01-03..2000-02-28');
  await expect(page.getByText(/^No Sundays with scores in /)).toBeVisible();
  await page
    .getByRole('group', { name: 'Widen the window' })
    .getByRole('button', { name: '12M' })
    .click();
  await expect(page).not.toHaveURL(/[?&]w=/);
  await expect(page.getByRole('list', { name: 'Standings' })).toBeVisible();
});

test('the rank chart fullscreen and CSV list the top 50 on every Sunday', async ({ page }) => {
  const anchor = await latestSunday(page);
  const query = `period=rolling_12&metric=season_points&from=${monthsBack(anchor, 12)}&to=${anchor}`;
  const everyone = await frames(page, `${query}&top=50`);
  const trimmed = await frames(page, `${query}&top=10`);
  const total = everyone.reduce((sum, f) => sum + f.rows.length, 0);
  const inline = trimmed.reduce((sum, f) => sum + f.rows.length, 0);
  expect(total).toBeGreaterThan(inline);

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/race?race-bump=table');
  const card = page.getByRole('region', { name: 'Rank over time' });
  await expect(card.getByRole('table').getByRole('row')).toHaveCount(1 + inline);
  await card.getByRole('button', { name: 'Fullscreen' }).click();
  const dialog = page.getByRole('dialog', { name: 'Rank over time' });
  await expect(dialog.getByText('The top 50 ranked on every Sunday.')).toBeVisible();
  await expect(dialog.getByRole('table').getByRole('row')).toHaveCount(1 + total);
  const download = page.waitForEvent('download');
  await dialog.getByRole('button', { name: 'CSV' }).click();
  const text = (await readFile(await (await download).path(), 'utf8')).replace(/^\uFEFF/, '');
  expect(text.trimEnd().split('\r\n')).toHaveLength(1 + total);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/race?race-bump=table,full');
  await expect(dialog.getByRole('table').getByRole('row')).toHaveCount(1 + total);
  await expectNoSideScroll(page);
});
