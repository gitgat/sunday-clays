import type { Page } from '@playwright/test';
import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

const section = (page: Page) => page.getByRole('region', { name: /^Summary card/ });
// The explainer's scope tag repeats the window, so text checks look inside the card itself.
const card = (page: Page) => section(page).getByRole('article');

// An active shooter by name, looked up through the API (ids differ between databases).
async function ike(page: Page): Promise<number> {
  const response = await page.request.get('/api/shooters?q=Hadley');
  expect(response.ok()).toBe(true);
  const rows = (await response.json()) as { shooter_id: number; display_name: string }[];
  const found = rows.find((r) => r.display_name === 'Hadley, Ike');
  expect(found).toBeDefined();
  return found?.shooter_id ?? 0;
}

test('3M shows the card with its window', async ({ page }) => {
  await page.goto(`/shooters/${await ike(page)}?w=3m`);
  await expect(section(page)).toBeVisible();
  await expect(card(page).getByText(/^Last 3 months · /)).toBeVisible();
  await expectNoSideScroll(page);
});

test('All sends no from and says "through"', async ({ page }) => {
  const asked = page.waitForRequest((r) => r.url().includes('/summary?'));
  await page.goto(`/shooters/${await ike(page)}?w=all`);
  expect(new URL((await asked).url()).searchParams.has('from')).toBe(false);
  await expect(card(page).getByText(/^All time · through /)).toBeVisible();
});

test('a custom window updates the dates', async ({ page }) => {
  await page.goto(`/shooters/${await ike(page)}?w=2025-01-05..2025-03-30`);
  await expect(card(page).getByText('Jan 5, 2025 – Mar 30, 2025')).toBeVisible();
});

test('Download image saves a PNG', async ({ page }) => {
  await page.goto(`/shooters/${await ike(page)}?w=12m`);
  await whenSettled(page);
  const download = page.waitForEvent('download');
  await section(page).getByRole('button', { name: 'Download image' }).click();
  expect((await download).suggestedFilename()).toMatch(/^sunday-clays-.*\.png$/);
});

test('an empty window offers 12M and All', async ({ page }) => {
  await page.goto(`/shooters/${await ike(page)}?w=2010-01-03..2010-02-28`);
  await expect(section(page).getByText('No Sundays shot in this window.')).toBeVisible();
  await expect(section(page).getByRole('button', { name: 'Show all time' })).toBeVisible();
});
