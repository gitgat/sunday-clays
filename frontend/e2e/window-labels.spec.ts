import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';
import { daysBack, longDate } from './window';

/** Every date and name below is read from the API at run time: no wall clock, no member names. */

const CHARTS = { timeout: 20_000 };
const EIGHT_WEEK_DAYS = 56;

async function lastScoreDate(page: Page): Promise<string> {
  const meta = (await (await page.request.get('/api/meta')).json()) as {
    last_score_date: string | null;
  };
  expect(meta.last_score_date).not.toBeNull();
  return meta.last_score_date as string;
}

/** A living shooter with the most rounds among those who shot nothing in the last 8 weeks. */
async function lapsedShooter(page: Page) {
  const last = await lastScoreDate(page);
  const since = daysBack(last, EIGHT_WEEK_DAYS - 1);
  const listed = (await (await page.request.get('/api/shooters')).json()) as {
    shooter_id: number;
    status: string;
    last_event: string;
    n_rounds: number;
  }[];
  const lapsed = listed.filter((s) => s.status !== 'deceased' && s.last_event < since);
  expect(lapsed.length, 'a shooter with no rounds in the last 8 weeks').toBeGreaterThan(0);
  return lapsed.reduce((a, b) => (b.n_rounds > a.n_rounds ? b : a));
}

test('a profile with no recent rounds says so and never draws all-time data under the window tag', async ({
  page,
}) => {
  const shooter = await lapsedShooter(page);
  await page.goto(`/shooters/${shooter.shooter_id}`);
  for (const title of ['Rating', 'Scores over time', 'Finishes']) {
    const card = page.getByRole('region', { name: title, exact: true });
    await expect(card.getByText(/^No rounds in the last 8 weeks \(/)).toBeVisible(CHARTS);
    await expect(card.getByText(`Last shot ${longDate(shooter.last_event)}.`)).toBeVisible();
    await expect(card.getByRole('img')).toHaveCount(0);
    // Table, CSV and Fullscreen stay reachable for every round.
    await expect(card.getByRole('button', { name: 'Fullscreen' })).toBeVisible();
    await expect(card.getByRole('button', { name: 'CSV' })).toBeVisible();
  }
  await whenSettled(page);
  await expectNoSideScroll(page);

  const rating = page.getByRole('region', { name: 'Rating', exact: true });
  await rating.getByRole('button', { name: 'Show all time' }).click();
  await expect(page).toHaveURL(/w=all/);
  await expect(rating.getByRole('img')).toBeVisible(CHARTS);
  await expect(rating.getByText(/^No rounds in/)).toHaveCount(0);
  await expectNoSideScroll(page);
});

test('the inline Table of a windowed chart lists the window only, and says so', async ({
  page,
}) => {
  const last = await lastScoreDate(page);
  const since = daysBack(last, EIGHT_WEEK_DAYS - 1);
  const trends = (await (await page.request.get('/api/club/trends')).json()) as {
    events: { event_date: string }[];
  };
  const inWindow = trends.events.filter((e) => e.event_date >= since && e.event_date <= last);
  expect(trends.events.length).toBeGreaterThan(inWindow.length);

  await page.goto('/club?scores=table');
  const card = page.getByRole('region', { name: 'Median and top score', exact: true });
  const rows = card.getByRole('row');
  await expect(rows).toHaveCount(inWindow.length + 1, CHARTS);
  await expect(
    card.getByText('Showing the time window. Open fullscreen or download CSV for every Sunday.'),
  ).toBeVisible();
  await expectNoSideScroll(page);
});

test('window tags carry their dates, and Custom shows its dates and how presets count', async ({
  page,
}) => {
  const last = await lastScoreDate(page);
  const since = daysBack(last, EIGHT_WEEK_DAYS - 1);
  await page.goto('/club');
  await expect(page.getByText(/^Last 8 weeks · /).first()).toContainText(
    longDate(since).replace(/, \d{4}$/, ''),
  );

  const custom = `${since}..${last}`;
  await page.goto(`/club?w=${custom}`);
  // The selected control shows the dates, not just "Custom": phones have no hover.
  const select = page.getByRole('combobox', { name: 'Time window' });
  if (await select.isVisible()) {
    await expect(select.locator('option:checked')).toHaveText(/\w{3} \d{1,2} – \w{3} \d{1,2}/);
    await select.selectOption('edit');
  } else {
    const group = page.getByRole('group', { name: 'Time window' });
    await expect(group.getByRole('button', { name: 'Custom' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await group.getByRole('button', { name: 'Custom' }).click();
  }
  const dialog = page.getByRole('dialog', { name: 'Custom dates' });
  await expect(dialog).toContainText('count back from the latest scored Sunday');
  await dialog.getByRole('button', { name: 'Back to last 8 weeks' }).click();
  await expect(page).not.toHaveURL(/\.\./);
  await expectNoSideScroll(page);
});

test('a Custom range across two years fits the phone top bar', async ({ page }) => {
  const last = await lastScoreDate(page);
  const from = daysBack(last, 400);
  await page.goto(`/club?w=${from}..${last}`);
  const select = page.getByRole('combobox', { name: 'Time window' });
  if (await select.isVisible()) {
    await expect(select.locator('option:checked')).toHaveText(/^\w{3} '\d\d – \w{3} '\d\d$/);
    const fits = await select.evaluate((el) => el.getBoundingClientRect().right <= innerWidth);
    expect(fits, 'select inside the viewport').toBe(true);
  }
  await expectNoSideScroll(page);
});
