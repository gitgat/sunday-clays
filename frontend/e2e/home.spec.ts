import { readFile } from 'node:fs/promises';

import { expect, test } from './fixtures';
import { expectNoSideScroll, expectTapTargets, whenSettled } from './layout';
import { longDate } from './window';

/**
 * `/` is the Sunday Sheet (Plan 14): the latest issue, with Home's rail (Your Sunday, Next
 * Sunday, Club pulse and the latest Sunday's details) beside the feed.
 */
interface Meta {
  first_event_date: string;
  last_score_date: string;
}

test('the front door is the latest Sunday Sheet, with the rail and the "Which one are you?" card', async ({
  page,
}) => {
  const meta = (await (await page.request.get('/api/meta')).json()) as Meta;
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'The Sunday Sheet' })).toBeVisible();
  await expect(
    page.getByRole('link', { name: `Full results, ${longDate(meta.last_score_date)}` }),
  ).toBeVisible();
  await expect(page.getByRole('region', { name: 'Which one are you?' })).toBeVisible();
  await expect(page.getByText('Turnout per Sunday', { exact: true })).toBeVisible();
});

test('the latest Sunday details link opens the full results', async ({ page }) => {
  const meta = (await (await page.request.get('/api/meta')).json()) as Meta;
  await page.goto('/');
  await page.getByRole('link', { name: /^Full results, / }).click();
  await expect(page).toHaveURL(new RegExp(`/events/${meta.last_score_date}$`));
});

test('every Sheet tap target is at least 44px with the "Which one are you?" card', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Which one are you?' })).toBeVisible();
  await whenSettled(page);
  await expectTapTargets(page);
});

test('every Sheet tap target is at least 44px with a me id', async ({ page }) => {
  const response = await page.request.get('/api/shooters?q=Hadley');
  expect(response.status()).toBe(200);
  const shooters = (await response.json()) as { shooter_id: number; display_name: string }[];
  const hadley = shooters.find((s) => s.display_name === 'Hadley, Ike');
  expect(hadley).toBeDefined();
  await page.addInitScript((id) => localStorage.setItem('sc.me', String(id)), hadley?.shooter_id);
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible();
  await expect(page.getByText('Last out')).toBeVisible();
  await whenSettled(page);
  await expectTapTargets(page);
});

test('the club pulse shows the 8 weeks up to the issue, whatever the time window says', async ({
  page,
}) => {
  const meta = (await (await page.request.get('/api/meta')).json()) as Meta;
  await page.goto('/?w=all');
  const pulse = page.getByRole('region', { name: 'Club pulse' });
  await expect(
    pulse.getByText(
      `8 weeks to ${longDate(meta.last_score_date)} · not affected by the time filter`,
    ),
  ).toBeVisible();
  const chart = page.getByRole('region', { name: 'Turnout per Sunday' });
  await chart.getByRole('button', { name: 'About this chart' }).click();
  await expect(chart.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  await expect(chart.getByText(/the Sheet always shows the 8 weeks/)).toBeVisible();
  await whenSettled(page);
  await expectNoSideScroll(page);
});

test('the turnout chart lists and exports every Sunday on record, not just the 8 weeks', async ({
  page,
}) => {
  // Every scored Sunday, year by year, read from the API at run time.
  const meta = (await (await page.request.get('/api/meta')).json()) as Meta;
  const first = Number(meta.first_event_date.slice(0, 4));
  const last = Number(meta.last_score_date.slice(0, 4));
  let scored = 0;
  for (let year = first; year <= last; year += 1) {
    const events = (await (await page.request.get(`/api/events?year=${year}`)).json()) as {
      has_scores: boolean;
    }[];
    scored += events.filter((e) => e.has_scores).length;
  }
  expect(scored).toBeGreaterThan(0);

  await page.goto('/');
  const chart = page.getByRole('region', { name: 'Turnout per Sunday' });
  const download = page.waitForEvent('download');
  await chart.getByRole('button', { name: 'CSV' }).click({ timeout: 15_000 });
  const file = await download;
  const text = (await readFile(await file.path(), 'utf8')).replace(/^\uFEFF/, '');
  expect(text.trimEnd().split('\r\n')).toHaveLength(scored + 1);

  await chart.getByRole('button', { name: 'Table' }).click();
  await expect(chart.getByRole('row').nth(1)).toBeVisible();
  const inlineRows = await chart.getByRole('row').count();
  expect(inlineRows - 1).toBeLessThan(scored);
  await page.setViewportSize({ width: 1440, height: 900 });
  await chart.getByRole('button', { name: 'Fullscreen' }).click();
  const dialog = page.getByRole('dialog', { name: 'Turnout per Sunday' });
  await expect(dialog.getByRole('row')).toHaveCount(scored + 1);
  await page.keyboard.press('Escape');

  await page.setViewportSize({ width: 390, height: 844 });
  await chart.getByRole('button', { name: 'Fullscreen' }).click();
  await expect(dialog.getByRole('row')).toHaveCount(scored + 1);
  await expectNoSideScroll(page);
});
