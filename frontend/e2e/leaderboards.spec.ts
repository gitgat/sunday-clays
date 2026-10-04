import { readFile } from 'node:fs/promises';

import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import {
  expectNoSideScroll,
  expectTapTargets,
  expectTitlesUntruncated,
  whenSettled,
} from './layout';
import { chooseWindow, datesText, longDate, monthsBack } from './window';

interface Board {
  period: string;
  min_rounds_applied: number;
  event_dates: string[];
  start: string | null;
  end: string;
  rows: { rank: number; shooter_id: number; display_name: string; value: number }[];
}

/** Expectations come from the API at run time: no wall clock, no hard-coded member names. */
async function board(page: Page, query: string): Promise<Board> {
  const response = await page.request.get(`/api/leaderboards?${query}`);
  expect(response.status()).toBe(200);
  return (await response.json()) as Board;
}

/** The season-final event of the year before the newest event, else the first event. */
function pastSeasonFinal(dates: string[]): string {
  const newest = dates.at(-1) ?? '';
  const previousYear = String(Number(newest.slice(0, 4)) - 1);
  return dates.filter((d) => d.startsWith(previousYear)).at(-1) ?? dates[0] ?? newest;
}

function standings(page: Page) {
  return page.getByRole('table', { name: 'Leaderboard standings' }).locator('tbody tr');
}

test('the Leaderboards nav entry opens the page', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Leaderboards' }).filter({ visible: true }).first().click();
  await expect(page).toHaveURL(/\/leaderboards/);
  await expect(page.getByRole('heading', { level: 1, name: 'Leaderboards' })).toBeVisible();
});

test('the all-time best-round board shows the API ranks, ties included, ten rows then Show all', async ({
  page,
}) => {
  const api = await board(page, 'period=all_time&metric=best_score');
  expect(api.rows.length).toBeGreaterThan(10);
  await page.goto('/leaderboards?w=all&metric=best_score');
  const rows = standings(page);
  await expect(rows).toHaveCount(10);
  for (const [i, row] of api.rows.slice(0, 6).entries()) {
    await expect(rows.nth(i).locator('td').nth(0)).toHaveText(String(row.rank));
    await expect(rows.nth(i).locator('td').nth(1)).toContainText(row.display_name);
    await expect(rows.nth(i).locator('td').nth(2)).toHaveText(String(Math.round(row.value)));
  }
  await page.getByRole('button', { name: `Show all ${String(api.rows.length)}` }).click();
  await expect(rows).toHaveCount(api.rows.length);
});

test('the header window is the only date control: each preset is the API board for that period', async ({
  page,
}) => {
  await page.goto('/leaderboards?metric=wins');
  await expect(page.getByRole('group', { name: 'Period' })).toHaveCount(0);
  await expect(page.getByLabel('Start date')).toHaveCount(0);
  for (const [preset, period] of [
    ['12m', 'rolling_12'],
    ['ytd', 'ytd'],
    ['all', 'all_time'],
    ['8w', 'season'],
  ] as const) {
    const api = await board(page, `period=${period}&metric=wins`);
    await chooseWindow(page, preset);
    // 8W is the default window, so the URL drops `w`; every other preset names itself.
    await expect
      .poll(() => new URL(page.url()).searchParams.get('w'))
      .toBe(preset === '8w' ? null : preset);
    await whenSettled(page);
    // The board keeps the previous preset's rows while the next loads, so a row count alone can
    // pass on stale rows: wait for this preset's names, in order.
    const rows = standings(page);
    await expect(rows.locator('td:nth-child(2)')).toContainText(
      api.rows.slice(0, 10).map((row) => row.display_name),
      { timeout: 15_000 },
    );
    if (preset !== 'all') {
      // The tag above the chart and table names the period and the dates the API resolved.
      const latest = api.event_dates.at(-1) ?? api.end;
      const start = api.start ?? api.event_dates[0] ?? api.end;
      await expect(page.getByText(` · ${datesText(start, api.end, latest)}`).first()).toBeVisible();
    }
  }
});

test('a 3M window sends a start date and matches the API board', async ({ page }) => {
  const { event_dates: dates } = await board(page, 'metric=wins');
  const latest = dates.at(-1) ?? '';
  const since = monthsBack(latest, 3);
  const api = await board(page, `since=${since}&metric=wins`);
  await page.goto('/leaderboards?w=3m&metric=wins');
  await expect(
    page.getByText(`Last 3 months · ${datesText(since, latest, latest)}`).first(),
  ).toBeVisible();
  const rows = standings(page);
  await expect(rows).toHaveCount(Math.min(10, api.rows.length));
  const top = api.rows[0];
  if (top !== undefined)
    await expect(rows.first().locator('td').nth(1)).toContainText(top.display_name);
});

test('a Custom window from Jan 1 is the same board as YTD', async ({ page }) => {
  const { event_dates: dates } = await board(page, 'metric=avg_score');
  const latest = dates.at(-1) ?? '';
  await page.goto('/leaderboards?w=ytd&metric=avg_score');
  const note = page.getByText(/^Needs ≥\d+ rounds · \d+ qualify$/);
  await expect(standings(page).first()).toBeVisible();
  await expect(note).toBeVisible();
  const ytdNote = await note.textContent();
  const ytdRows = await standings(page).allTextContents();
  await page.goto(`/leaderboards?w=${latest.slice(0, 4)}-01-01..${latest}&metric=avg_score`);
  await expect(standings(page).first()).toBeVisible();
  await expect(note).toHaveText(ytdNote ?? '');
  expect(await standings(page).allTextContents()).toEqual(ytdRows);
});

test('Board as of steps a Sunday at a time, snaps to event dates and returns to the latest', async ({
  page,
}) => {
  const { event_dates: dates } = await board(page, 'period=ytd&metric=season_points');
  const target = pastSeasonFinal(dates);
  const expected = await board(page, `period=ytd&metric=season_points&as_of=${target}`);
  await page.goto(`/leaderboards?w=ytd&metric=season_points&as_of=${target}`);
  await expect(page.locator('output', { hasText: longDate(target) })).toBeVisible();
  const first = expected.rows[0];
  if (first === undefined) throw new Error(`no season points rows as of ${target}`);
  await expect(standings(page).first().locator('td').nth(2)).toHaveText(
    String(Math.round(first.value)),
  );

  // Scrubbing to the first event lands on exactly that event date (never between events).
  const earliest = dates[0] ?? target;
  await page.getByLabel('Board as of').fill('0');
  await expect(page.locator('output', { hasText: longDate(earliest) })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`as_of=${earliest}`));

  // ▶ moves one Sunday on.
  const second = dates[1] ?? earliest;
  await page.getByRole('button', { name: 'Next Sunday' }).click();
  await expect(page).toHaveURL(new RegExp(`as_of=${second}`));
  await page.getByRole('button', { name: 'Previous Sunday' }).click();
  await expect(page).toHaveURL(new RegExp(`as_of=${earliest}`));

  await page.getByRole('button', { name: 'Latest' }).click();
  await expect(page.locator('output').filter({ hasText: /^Latest$/ })).toBeVisible();
  await expect(page).not.toHaveURL(/as_of=/);
});

test('Board as of is hidden for a Custom window', async ({ page }) => {
  const { event_dates: dates } = await board(page, 'metric=wins');
  const from = dates.at(-6) ?? '';
  const to = dates.at(-2) ?? '';
  await page.goto(`/leaderboards?w=${from}..${to}&metric=wins`);
  await expect(standings(page).first()).toBeVisible();
  await expect(page.getByLabel('Board as of')).toHaveCount(0);
  const api = await board(page, `since=${from}&as_of=${to}&metric=wins`);
  await expect(standings(page)).toHaveCount(Math.min(10, api.rows.length));
  await expect(
    page.locator('main').getByText(datesText(from, to, dates.at(-1) ?? to), { exact: true }),
  ).toBeVisible();
});

test('rating gain replaces the rating ranking: only gainers, and old links convert', async ({
  page,
}) => {
  const api = await board(page, 'period=rolling_12&metric=rating_gain');
  expect(api.rows.length).toBeGreaterThan(0);
  expect(api.rows.every((row) => row.value > 0)).toBe(true);
  await page.goto('/leaderboards?w=12m&metric=rating');
  await expect(page).toHaveURL(/metric=rating_gain/);
  await expect(page).not.toHaveURL(/metric=rating(&|$)/);
  await expect(standings(page)).toHaveCount(Math.min(10, api.rows.length));
  const top = api.rows[0];
  if (top !== undefined)
    await expect(standings(page).first().locator('td').nth(1)).toContainText(top.display_name);
  await expect(
    page.getByRole('table', { name: 'Leaderboard standings' }).getByRole('columnheader', {
      name: 'Rating gain',
    }),
  ).toBeVisible();
  await expect(page.getByRole('main').getByText('Most improved', { exact: true })).toHaveCount(0);
});

test('old Leaderboards links convert once into the window and leave the URL', async ({ page }) => {
  const api = await board(page, 'period=rolling_12&metric=wins');
  await page.goto('/leaderboards?period=rolling_12&metric=wins');
  await expect(page).toHaveURL(/[?&]w=12m(&|$)/);
  await expect(page).not.toHaveURL(/period=/);
  await expect(standings(page)).toHaveCount(Math.min(10, api.rows.length));
});

test('an empty window says so in plain words and widens to 12M in one tap', async ({ page }) => {
  await page.goto('/leaderboards?w=2000-01-03..2000-02-28&metric=wins');
  await expect(page.getByText(/^No Sundays with scores in /)).toBeVisible();
  const widen = page.getByRole('group', { name: 'Widen the window' });
  await widen.getByRole('button', { name: '12M' }).click();
  await expect(page).toHaveURL(/[?&]w=12m(&|$)/);
  await expect(standings(page).first()).toBeVisible();
});

test('the leaders chart offers table and CSV views', async ({ page }) => {
  await page.goto('/leaderboards?w=all&metric=wins');
  const chart = page.getByRole('region', { name: /^Top \d+ · Wins$/ });
  await expect(chart.getByRole('button', { name: 'CSV' })).toBeVisible();
  await chart.getByRole('button', { name: 'Table' }).click();
  await expect(chart.getByRole('table')).toBeVisible();
});

test('the leaders chart is tagged with its window, not All time, and explains itself', async ({
  page,
}) => {
  await page.goto('/leaderboards?metric=season_points');
  const chart = page.getByRole('region', { name: /^Top \d+ · Points$/ });
  await chart.getByRole('button', { name: 'About this chart' }).click();
  await expect(chart.getByRole('heading', { name: "How it's worked out" })).toBeVisible();
  await expect(chart.getByText(/^Last 8 weeks · /).first()).toBeVisible();
  await expect(chart.getByText('All time', { exact: true })).toHaveCount(0);
  const table = page.getByRole('table', { name: 'Leaderboard standings' });
  await expect(table.getByRole('columnheader', { name: 'Sundays' })).toBeVisible();
  await expect(table.locator('[aria-label^="Class "]')).toHaveCount(0);
});

test('non-Sunday boards count Rounds, and the classes endpoint is gone', async ({ page }) => {
  await page.goto('/leaderboards?w=all&metric=wins');
  await expect(
    page.getByRole('table', { name: 'Leaderboard standings' }).getByRole('columnheader', {
      name: 'Rounds',
    }),
  ).toBeVisible();
  expect((await page.request.get('/api/classes')).status()).toBe(404);
});

test('shooter links keep the round-type filter', async ({ page }) => {
  await page.goto('/leaderboards?w=all&metric=rounds&rt=super_sporting');
  await expect(standings(page).first().getByRole('link')).toHaveCSS(
    'text-decoration-line',
    'underline',
  );
  await standings(page).first().getByRole('link').click();
  // The link keeps the round type and the time window.
  await expect(page).toHaveURL(/\/shooters\/\d+\?rt=super_sporting&w=all$/);
});

test('the page fits the viewport, phones get a measure select, and every tap target is at least 44px', async ({
  page,
}, testInfo) => {
  await page.goto('/leaderboards?w=all&metric=avg_score');
  await expect(standings(page).first()).toBeVisible();
  await expectNoSideScroll(page);
  // The standings table must fit its own scroll wrapper too, not just the document.
  const wrapper = await page
    .getByRole('table', { name: 'Leaderboard standings' })
    .evaluate((table) => ({
      scroll: table.parentElement?.scrollWidth ?? 0,
      client: table.parentElement?.clientWidth ?? 0,
    }));
  expect(wrapper.scroll).toBeLessThanOrEqual(wrapper.client);

  // The measure chips collapse into a select on a phone.
  const select = page.getByRole('combobox', { name: 'Measure' });
  const chips = page.getByRole('group', { name: 'Measure' });
  if (testInfo.project.name === 'mobile') {
    await expect(select).toBeVisible();
    await expect(chips).toBeHidden();
  } else {
    await expect(select).toBeHidden();
    await expect(chips).toBeVisible();
  }

  const small: string[] = [];
  for (const target of await page.getByRole('main').locator('a, button, select, input').all()) {
    if (!(await target.isVisible())) continue;
    const box = await target.boundingBox();
    if (box === null || box.height < 44 || box.width < 44) {
      const name =
        (await target.textContent())?.trim() || (await target.getAttribute('aria-label'));
      small.push(`${name}: ${box === null ? 'no box' : `${box.width}×${box.height}`}`);
    }
  }
  expect(small).toEqual([]);
  await expectTapTargets(page);
  await expectTitlesUntruncated(page);
});

test('fullscreen and the CSV list everyone in the standings, not only the top ten', async ({
  page,
}) => {
  const api = await board(page, 'period=all_time&metric=rounds');
  expect(api.rows.length).toBeGreaterThan(10);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/leaderboards?w=all&metric=rounds&lb-chart=table');
  const card = page.getByRole('region', { name: /^Top 10 · Rounds$/ });
  await expect(card.getByRole('table').getByRole('row')).toHaveCount(1 + 10);
  await card.getByRole('button', { name: 'Fullscreen' }).click();
  const dialog = page.getByRole('dialog', { name: /^Top 10 · Rounds$/ });
  await expect(dialog.getByText('Everyone in the standings.')).toBeVisible();
  await expect(dialog.getByRole('table').getByRole('row')).toHaveCount(1 + api.rows.length);
  const download = page.waitForEvent('download');
  await dialog.getByRole('button', { name: 'CSV' }).click();
  const text = (await readFile(await (await download).path(), 'utf8')).replace(/^\uFEFF/, '');
  expect(text.trimEnd().split('\r\n')).toHaveLength(1 + api.rows.length);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/leaderboards?w=all&metric=rounds&lb-chart=table,full');
  await expect(
    page
      .getByRole('dialog', { name: /^Top 10 · Rounds$/ })
      .getByRole('table')
      .getByRole('row'),
  ).toHaveCount(1 + api.rows.length);
  await expectNoSideScroll(page);
});
