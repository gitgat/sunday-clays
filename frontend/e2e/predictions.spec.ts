import type { Page } from '@playwright/test';
import { expect, test } from './fixtures';
import { expectNoSideScroll, expectTapTargets, expectTitlesUntruncated } from './layout';

// Runs in the `mobile` (390) and `desktop` (1440) projects as the seeded viewer. compose.test.yaml
// sets WEATHER_ENABLED=false, so there is never a forecast. Expectations are read from the API at
// run time: which shooters have one depends on the date the suite runs.
interface Predictions {
  target_date: string;
  model_ready: boolean;
  forecast: unknown;
  shooters: { shooter_id: number; expected: number; sd: number }[];
}

async function predictions(page: Page): Promise<Predictions> {
  const response = await page.request.get('/api/predictions/next');
  expect(response.ok()).toBe(true);
  return (await response.json()) as Predictions;
}

// The whole suite shares one API: other specs' rebuilds can slow every page, so allow for that.
async function settled(page: Page): Promise<void> {
  await expect(page.getByRole('status')).toHaveCount(0, { timeout: 30_000 });
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0, { timeout: 30_000 });
}

const whole = (value: number): string => String(Math.round(Math.min(50, Math.max(0, value))));

test('home shows the Next Sunday card without a forecast', async ({ page }) => {
  const api = await predictions(page);
  expect(api.forecast).toBeNull();
  await page.goto('/');
  const card = page.getByRole('region', { name: 'Next Sunday', exact: true });
  await expect(
    card.getByText('No forecast yet. It appears a few days before the shoot.'),
  ).toBeVisible();
  await expect(card.getByText('Predicted field median')).toBeVisible();
  await expect(card.getByText('Expected turnout')).toBeVisible();
  await expect(card.getByText(/Pick your name in “Which one are you\?”/)).toBeVisible();
  await card.getByRole('button', { name: 'About these predictions' }).click();
  await expect(card.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  await expect(card.getByRole('heading', { name: "How it's worked out" })).toBeVisible();
  await settled(page);
  await expectNoSideScroll(page);
  await expectTitlesUntruncated(page);
  await expectTapTargets(page);
});

test('a viewer who is “me” sees their own expected score on home', async ({ page }) => {
  const api = await predictions(page);
  expect(api.shooters.length).toBeGreaterThan(0);
  const mine = api.shooters[0];
  if (mine === undefined) throw new Error('the seeded fixtures have no expected scores');
  const id = mine.shooter_id;
  await page.addInitScript((value) => localStorage.setItem('sc.me', String(value)), id);
  await page.goto('/');
  const card = page.getByRole('region', { name: 'Next Sunday', exact: true });
  await expect(
    card.getByText(
      `Expected around ${whole(mine.expected)} next Sunday, likely ${whole(mine.expected - mine.sd)}–${whole(mine.expected + mine.sd)}.`,
    ),
  ).toBeVisible();
  await settled(page);
  await expectNoSideScroll(page);
  await expectTapTargets(page);
});

test('a profile shows that shooter’s own expectation', async ({ page }) => {
  const api = await predictions(page);
  expect(api.shooters.length).toBeGreaterThan(0);
  const mine = api.shooters[0];
  if (mine === undefined) throw new Error('the seeded fixtures have no expected scores');
  const id = mine.shooter_id;
  await page.goto(`/shooters/${id}`);
  const outlook = page.getByRole('region', { name: 'Next Sunday outlook' });
  await expect(
    outlook.getByText(
      `Expected around ${whole(mine.expected)} next Sunday, likely ${whole(mine.expected - mine.sd)}–${whole(mine.expected + mine.sd)}.`,
    ),
  ).toBeVisible();
  await outlook.getByRole('button', { name: 'About this expected score' }).click();
  await expect(outlook.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  await settled(page);
  await expectNoSideScroll(page);
  await expectTitlesUntruncated(page);
  await expectTapTargets(page);
});
