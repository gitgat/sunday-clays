import { readFile } from 'node:fs/promises';

import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';

// A profile mounts six lazy charts (ECharts loads on demand), which can take longer than the
// default 5 s to appear when many workers share one stack. Only the waits for those charts get this.
const CHARTS = { timeout: 20_000 };

interface Listed {
  shooter_id: number;
  display_name: string;
  status: string;
  n_rounds: number;
}

/** The living shooter with the most rounds, read from the API: no member name or date is hard-coded. */
async function pickShooter(page: Page) {
  const listed = await page.request.get('/api/shooters');
  expect(listed.status()).toBe(200);
  const shooters = ((await listed.json()) as Listed[]).filter((s) => s.status !== 'deceased');
  const chosen = shooters.reduce((a, b) => (b.n_rounds > a.n_rounds ? b : a));
  const detail = await page.request.get(`/api/shooters/${chosen.shooter_id}`);
  expect(detail.status()).toBe(200);
  const { pbs } = (await detail.json()) as {
    pbs: { scope: string; score: number }[];
  };
  const rounds = await page.request.get(`/api/shooters/${chosen.shooter_id}/rounds`);
  expect(rounds.status()).toBe(200);
  const dates = ((await rounds.json()) as { event_date: string }[]).map((r) => r.event_date);
  const latestYear = dates.reduce((a, b) => (b > a ? b : a)).slice(0, 4);
  const overall = pbs.find((p) => p.scope === 'overall');
  expect(overall, 'the busiest shooter has an overall personal best').toBeDefined();
  return { ...chosen, latestYear, overallBest: String(overall?.score) };
}

test('a long-time shooter profile shows every chart and the personal-best table', async ({
  page,
}) => {
  const shooter = await pickShooter(page);
  await page.goto(`/shooters/${shooter.shooter_id}`);
  await expect(page.getByRole('heading', { level: 1, name: shooter.display_name })).toBeVisible();
  for (const title of [
    'Rating',
    'Scores over time',
    'Score distribution vs club',
    'Learning curve vs club',
    'Splits by Year',
    `Attendance calendar ${shooter.latestYear}`,
  ]) {
    const region = page.getByRole('region', { name: title, exact: true });
    await expect(region).toBeVisible(CHARTS);
    // Scoped per chart: other features add their own profile sections (and charts) below.
    await expect(region.getByRole('button', { name: 'CSV' })).toHaveCount(1, CHARTS);
    await expect(region.getByRole('button', { name: 'About this chart' })).toBeVisible();
  }
  // Rating and the learning curve ignore the round-type filter and say so.
  await expect(
    page.getByRole('region', { name: 'Rating', exact: true }).getByText('All round types'),
  ).toBeVisible();
  await expect(
    page.getByRole('table', { name: 'Personal bests' }).getByRole('row', { name: /Overall/ }),
  ).toContainText(shooter.overallBest);
});

test('the personal-best date links are underlined with a 44 px tap target', async ({ page }) => {
  const shooter = await pickShooter(page);
  await page.goto(`/shooters/${shooter.shooter_id}`);
  const links = page.getByRole('table', { name: 'Personal bests' }).getByRole('link');
  await expect(links.first()).toBeVisible();
  for (const link of await links.all()) {
    const box = await link.boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(44);
    expect(box?.width).toBeGreaterThanOrEqual(44);
  }
  await expect(links.first()).toHaveCSS('text-decoration-line', 'underline');
});

test('the profile does not scroll sideways', async ({ page }) => {
  const shooter = await pickShooter(page);
  await page.goto(`/shooters/${shooter.shooter_id}`);
  // At least the six profile charts have loaded (other profile sections may add more).
  await expect(page.getByRole('button', { name: 'CSV' }).nth(5)).toBeVisible(CHARTS);
  await expect(page.getByRole('table', { name: 'Personal bests' })).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test('the split chips switch the splits chart', async ({ page }) => {
  const shooter = await pickShooter(page);
  await page.goto(`/shooters/${shooter.shooter_id}`);
  const chips = page
    .getByRole('region', { name: /^Splits by / })
    .getByRole('group', { name: 'Split by' });
  await chips.getByRole('button', { name: 'Gauge', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Splits by Gauge', exact: true })).toBeVisible();
  await expect(page).toHaveURL(/split=gauge/);
  await expect(chips.getByRole('button', { name: 'Gauge', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
});

test('the explainers open without sideways scroll and the profile says Sundays, not events', async ({
  page,
}) => {
  const shooter = await pickShooter(page);
  await page.goto(`/shooters/${shooter.shooter_id}`);
  const rating = page.getByRole('region', { name: 'Rating', exact: true });
  await rating.getByRole('button', { name: 'About this chart' }).click();
  await expect(rating.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  const insights = page.getByRole('region', { name: 'Stats', exact: true });
  await insights.getByRole('button', { name: 'About Rust' }).click();
  await expect(insights.getByRole('heading', { name: "How it's worked out" })).toBeVisible();
  const hero = page.locator('header').filter({ has: page.getByRole('heading', { level: 1 }) });
  await expect(hero.getByText('Sundays', { exact: true })).toBeVisible();
  await expect(hero.getByText('Events', { exact: true })).toHaveCount(0);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test('fullscreen and the CSV show every round and every year', async ({ page }) => {
  const shooter = await pickShooter(page);
  const rounds = (await (
    await page.request.get(`/api/shooters/${shooter.shooter_id}/rounds`)
  ).json()) as {
    event_date: string;
  }[];
  const shotDates = new Set(rounds.map((r) => r.event_date));
  const years = [...new Set(rounds.map((r) => r.event_date.slice(0, 4)))];
  let missed = 0;
  for (const year of years) {
    const held = (await (await page.request.get(`/api/events?year=${year}`)).json()) as {
      event_date: string;
      results_complete: boolean;
    }[];
    missed += held.filter((e) => e.results_complete && !shotDates.has(e.event_date)).length;
  }

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/shooters/${shooter.shooter_id}?trend=table`);
  const trend = page.getByRole('region', { name: 'Scores over time', exact: true });
  await expect(trend.getByRole('table')).toBeVisible(CHARTS);
  await trend.getByRole('button', { name: 'Fullscreen' }).click();
  const dialog = page.getByRole('dialog', { name: 'Scores over time' });
  // Header row plus one row per round, from /rounds.
  await expect(dialog.getByRole('row')).toHaveCount(rounds.length + 1, CHARTS);
  const trendDownload = page.waitForEvent('download');
  await dialog.getByRole('button', { name: 'CSV' }).click();
  const trendText = (await readFile(await (await trendDownload).path(), 'utf8')).slice(1);
  expect(trendText.trimEnd().split('\r\n')).toHaveLength(rounds.length + 1);
  await dialog.getByRole('button', { name: 'Close' }).click();

  const cal = page.getByRole('region', { name: /^Attendance calendar \d{4}$/ });
  const calDownload = page.waitForEvent('download');
  await cal.getByRole('button', { name: 'CSV' }).click();
  const calText = (await readFile(await (await calDownload).path(), 'utf8')).slice(1);
  expect(calText.trimEnd().split('\r\n')).toHaveLength(1 + shotDates.size + missed);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/shooters/${shooter.shooter_id}?trend=table,full`);
  await expect(page.getByRole('dialog', { name: 'Scores over time' }).getByRole('row')).toHaveCount(
    rounds.length + 1,
    CHARTS,
  );
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
