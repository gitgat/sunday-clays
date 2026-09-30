import { readFile } from 'node:fs/promises';

import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import { expectNoSideScroll, expectTapTargets, expectTitlesUntruncated } from './layout';
import { chooseWindow, daysBack, datesText, monthsBack } from './window';

interface RecordRound {
  rank: number;
  shooter_id: number;
  display_name: string;
  event_date: string;
  value: number;
}

interface Records {
  as_of: string;
  highest_scores: RecordRound[];
  perfect_rounds: RecordRound[];
  most_events: { value: number }[];
  longest_streaks: unknown[];
  totals: Record<string, number>;
  tied_more: Record<string, number>;
}

/** Expectations come from the API at run time (never hard-coded names or counts). */
async function fetchRecords(page: Page, params: Record<string, string> = {}): Promise<Records> {
  const response = await page.request.get('/api/records', { params });
  expect(response.ok()).toBe(true);
  return (await response.json()) as Records;
}

/** The latest scored Sunday, from the API (never the wall clock). */
async function latestSunday(page: Page): Promise<string> {
  const { as_of } = await fetchRecords(page);
  return as_of;
}

const CHARTS = { timeout: 20_000 };

test('records default to the last 8 weeks and match the API for those dates', async ({ page }) => {
  const latest = await latestSunday(page);
  const since = daysBack(latest, 55);
  const api = await fetchRecords(page, { since, as_of: latest });
  await page.goto('/records');
  await expect(page.getByRole('heading', { level: 1, name: 'Records' })).toBeVisible();
  await expect(page).not.toHaveURL(/[?&]w=/);
  // One date control: the header window. Records has no period buttons or date inputs of its own.
  await expect(page.getByRole('group', { name: 'Dates' })).toHaveCount(0);
  await expect(page.getByLabel('Start date')).toHaveCount(0);
  const tag = `Last 8 weeks · ${datesText(since, latest, latest)}`;
  await expect(page.getByText(tag, { exact: true }).first()).toBeVisible();
  const rows = page.getByRole('table', { name: 'Highest scores' }).locator('tbody tr');
  await expect(rows).toHaveCount(api.highest_scores.length);
  const top = api.highest_scores[0];
  if (top === undefined) throw new Error('the fixtures have rounds in the last 8 weeks');
  await expect(rows.first().locator('td').nth(2)).toHaveText(String(top.value));
  // The period is in every card subtitle.
  for (const name of [
    'Highest scores',
    'Perfect 50s',
    'Biggest day vs the field',
    'Most Sundays shot',
    'Longest streaks',
  ]) {
    await expect(page.getByRole('region', { name }).getByText(tag).first()).toBeVisible();
  }
});

test('all-time records: perfect 50s newest first, ten rows then Show all, ties named', async ({
  page,
}) => {
  const api = await fetchRecords(page);
  // Fixture facts (Plan 09 D22) pinned so a backend regression cannot pass by the page echoing it.
  expect(api.perfect_rounds).toHaveLength(6);
  expect(api.highest_scores[0]?.value).toBe(50);
  await page.goto('/records?w=all');
  const perfect = page.getByRole('region', { name: 'Perfect 50s' });
  const items = perfect.getByRole('listitem');
  await expect(items).toHaveCount(api.perfect_rounds.length);
  const newest = api.perfect_rounds[0];
  if (newest === undefined) throw new Error('the fixtures have a perfect round');
  expect(api.perfect_rounds.map((r) => r.event_date)).toEqual(
    [...api.perfect_rounds.map((r) => r.event_date)].sort().reverse(),
  );
  await expect(items.first().getByRole('link').first()).toHaveText(newest.display_name);

  const scores = page.getByRole('region', { name: 'Highest scores' });
  const rows = scores.getByRole('table', { name: 'Highest scores' }).locator('tbody tr');
  await expect(rows).toHaveCount(10);
  const total = api.totals['highest_scores'] ?? 0;
  expect(total).toBeGreaterThan(10);
  const tied = api.tied_more['highest_scores'] ?? 0;
  if (tied > 0)
    await expect(scores.getByText(new RegExp(`^${String(tied)} more tied at `))).toBeVisible();
  const shownAll = Math.min(total, 500);
  await scores
    .getByRole('button', {
      name: total > 500 ? `Show top 500 of ${String(total)}` : `Show all ${String(total)}`,
    })
    .click();
  await expect(rows).toHaveCount(shownAll);
  await scores.getByRole('button', { name: 'Show fewer' }).click();
  await expect(rows).toHaveCount(10);
});

test('the chart cards keep table and CSV, and the explainer is tagged with the window', async ({
  page,
}) => {
  await page.goto('/records');
  const events = page.getByRole('region', { name: 'Most Sundays shot' });
  await expect(events.getByRole('button', { name: /csv/i })).toBeVisible();
  await expect(events.getByRole('img', { name: 'Most Sundays shot bar chart' })).toBeVisible(
    CHARTS,
  );
  await events.getByRole('button', { name: 'Table' }).click();
  await expect(page).toHaveURL(/rec-events=table/);
  await expect(events.getByRole('table', { name: 'Most Sundays shot' })).toBeVisible();
  const about = events.getByRole('button', { name: 'About this chart' });
  await about.click();
  await expect(events.getByRole('heading', { name: "How it's worked out" })).toBeVisible();
  await expect(events.getByText(/^Last 8 weeks · /).first()).toBeVisible();
  await expect(events.getByText('All time', { exact: true })).toHaveCount(0);
  await about.click();
  await expect(events.getByRole('heading', { name: 'What this shows' })).toBeHidden();
  await expect(
    page.getByRole('region', { name: 'Biggest jump from one Sunday to the next' }),
  ).toBeVisible();
  await expect(page.getByRole('main')).not.toContainText(/week-over-week|median/i);
});

test('choosing 12M in the header asks for twelve months of records', async ({ page }) => {
  const latest = await latestSunday(page);
  const since = monthsBack(latest, 12);
  const api = await fetchRecords(page, { since, as_of: latest });
  await page.goto('/records');
  await expect(page.getByRole('table', { name: 'Highest scores' })).toBeVisible();
  await chooseWindow(page, '12m');
  await expect(page).toHaveURL(/[?&]w=12m(&|$)/);
  await expect(
    page.getByText(`Last 12 months · ${datesText(since, latest, latest)}`, { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByRole('table', { name: 'Highest scores' }).locator('tbody tr')).toHaveCount(
    api.highest_scores.length,
  );
});

test('old Records links convert once into the window', async ({ page }) => {
  const latest = await latestSunday(page);
  await page.goto('/records?rp=ytd&rt=sporting');
  await expect(page).toHaveURL(/[?&]w=ytd(&|$)/);
  await expect(page).not.toHaveURL(/rp=/);
  await expect(page).toHaveURL(/rt=sporting/);
  await expect(
    page
      .getByText(
        `This year to date · ${datesText(`${latest.slice(0, 4)}-01-01`, latest, latest)}`,
        {
          exact: true,
        },
      )
      .first(),
  ).toBeVisible();
  await page.goto('/records?rp=all');
  await expect(page).toHaveURL(/[?&]w=all(&|$)/);
  await page.goto(
    `/records?rp=custom&since=${daysBack(latest, 100)}&as_of=${daysBack(latest, 30)}`,
  );
  await expect(page).toHaveURL(
    new RegExp(`[?&]w=${daysBack(latest, 100)}\\.\\.${daysBack(latest, 30)}(&|$)`),
  );
  await expect(page).not.toHaveURL(/since=|as_of=|rp=/);
});

test('a window with no rounds says so in plain words and widens to 12M in one tap', async ({
  page,
}) => {
  await page.goto('/records?w=2000-01-03..2000-02-28');
  await expect(page.getByText(/^No scored rounds in /)).toBeVisible();
  await expect(page.getByRole('table', { name: 'Highest scores' })).toHaveCount(0);
  await page
    .getByRole('group', { name: 'Widen the window' })
    .getByRole('button', { name: '12M' })
    .click();
  await expect(page).toHaveURL(/[?&]w=12m(&|$)/);
  await expect(page.getByRole('table', { name: 'Highest scores' })).toBeVisible();
});

test('the super sporting filter follows the API and stays on links', async ({ page }) => {
  const all = await fetchRecords(page);
  const records = await fetchRecords(page, { round_type: 'super_sporting' });
  // Fixture facts (Plan 09 D22): the two super sporting Sundays have no 50 and a top score of 48.
  expect(records.perfect_rounds).toHaveLength(0);
  expect(records.highest_scores[0]?.value).toBe(48);
  await page.goto('/records?w=all&rt=super_sporting');
  const perfect = page.getByRole('region', { name: 'Perfect 50s' });
  await expect(perfect.getByText('None yet')).toBeVisible();
  const table = page.getByRole('table', { name: 'Highest scores' });
  await expect(table.locator('tbody tr')).toHaveCount(records.highest_scores.length);
  await expect(table.locator('tbody tr').first().locator('td').nth(2)).toHaveText(
    String(records.highest_scores[0]?.value),
  );
  expect(records.highest_scores[0]?.value).toBeLessThan(all.highest_scores[0]?.value ?? 0);
  const links = await table
    .getByRole('link')
    .evaluateAll((els) => els.map((el) => el.getAttribute('href') ?? ''));
  expect(links.length).toBeGreaterThan(0);
  for (const href of links) expect(href).toContain('rt=super_sporting');
});

test('records fit the viewport, keep 44 px targets and an unbroken heading outline', async ({
  page,
}) => {
  await page.goto('/records?w=all');
  await expect(page.getByRole('heading', { level: 1, name: 'Records' })).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'Most Sundays shot' }).getByRole('img'),
  ).toBeVisible(CHARTS);
  await expectNoSideScroll(page);
  await expectTapTargets(page);
  await expectTitlesUntruncated(page);

  const levels = await page
    .locator('main')
    .locator('h1, h2, h3, h4, h5, h6')
    .evaluateAll((elements) => elements.map((el) => Number(el.tagName.slice(1))));
  expect(levels[0], `outline ${levels.join(' ')}`).toBe(1);
  expect(
    levels.filter((level, i) => i > 0 && level > (levels[i - 1] ?? 0) + 1),
    `outline ${levels.join(' ')}`,
  ).toEqual([]);
});

test('fullscreen and the CSV list every shooter, not only the top ten', async ({ page }) => {
  const latest = await latestSunday(page);
  const all = await fetchRecords(page, { limit: 'all', as_of: latest });
  expect(all.most_events.length).toBeGreaterThan(10);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/records?w=all&rec-events=table');
  const card = page.getByRole('region', { name: 'Most Sundays shot' });
  await expect(card.getByRole('table')).toBeVisible();
  await expect(card.getByRole('table').getByRole('row')).toHaveCount(1 + 10);
  await card.getByRole('button', { name: 'Fullscreen' }).click();
  const dialog = page.getByRole('dialog', { name: 'Most Sundays shot' });
  await expect(dialog.getByText('Every shooter.')).toBeVisible();
  await expect(dialog.getByRole('table').getByRole('row')).toHaveCount(1 + all.most_events.length);
  const download = page.waitForEvent('download');
  await dialog.getByRole('button', { name: 'CSV' }).click();
  const text = (await readFile(await (await download).path(), 'utf8')).replace(/^\uFEFF/, '');
  expect(text.trimEnd().split('\r\n')).toHaveLength(1 + all.most_events.length);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/records?w=all&rec-streaks=table,full');
  await expect(
    page.getByRole('dialog', { name: 'Longest streaks' }).getByRole('table').getByRole('row'),
  ).toHaveCount(1 + all.longest_streaks.length);
  await expectNoSideScroll(page);
});
