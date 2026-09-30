import type { Locator, Page } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { expect, test } from './fixtures';
import { expectNoSideScroll, expectTapTargets, whenSettled } from './layout';

// Headless Chromium may expose the Web Share API; remove it so lib/share.ts always downloads.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'share', { value: undefined, configurable: true });
    Object.defineProperty(navigator, 'canShare', { value: undefined, configurable: true });
  });
});

interface EventSummary {
  event_date: string;
  has_scores: boolean;
}
interface EventDetail {
  results: { display_name: string; is_best_round: boolean; event_rank: number | null }[];
}
interface ShooterRow {
  shooter_id: number;
  display_name: string;
}
interface ShooterDetail {
  display_name: string;
  odometer: { clays_broken: number };
}
interface Trophy {
  code: string;
  holders: number;
}

// Expectations come from the API at run time, never from hard-coded fixture values.
async function getJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), path).toBe(true);
  return (await response.json()) as T;
}

const slug = (text: string): string =>
  text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');

/** Clicks the button, waits for the download and checks the file really is a PNG. */
async function download(page: Page, button: Locator): Promise<string> {
  await expect(button).toBeEnabled();
  const pending = page.waitForEvent('download');
  await button.click();
  const file = await pending;
  const path = await file.path();
  const bytes = await readFile(path);
  expect([...bytes.subarray(1, 4)], 'PNG signature').toEqual([0x50, 0x4e, 0x47]);
  return file.suggestedFilename();
}

async function fitsTheScreen(page: Page): Promise<void> {
  await whenSettled(page);
  await expectNoSideScroll(page);
  await expectTapTargets(page);
}

test('the Sunday results card downloads as an image', async ({ page }) => {
  const { years } = await getJson<{ years: number[] }>(page, '/api/yir/2000');
  const summaries = await getJson<EventSummary[]>(
    page,
    `/api/events?year=${years[years.length - 1]}`,
  );
  const sunday = summaries.filter((e) => e.has_scores).at(-1);
  if (sunday === undefined) throw new Error('the seeded fixtures have no scored Sunday');
  const detail = await getJson<EventDetail>(page, `/api/events/${sunday.event_date}`);
  const winner = detail.results.find((r) => r.is_best_round && r.event_rank === 1);
  if (winner === undefined) throw new Error('the scored Sunday has no winner');

  await page.goto(`/events/${sunday.event_date}`);
  const section = page.getByRole('region', { name: 'Shareable results card' });
  await expect(section.getByText(winner.display_name).first()).toBeVisible();
  const name = await download(page, section.getByRole('button', { name: 'Share image' }));
  expect(name).toBe(`sunday-clays-${sunday.event_date}.png`);
  await expect(section.getByText('Image ready.')).toBeVisible();
  await fitsTheScreen(page);
});

test('the profile card downloads as an image and shows the odometer', async ({ page }) => {
  const [first] = await getJson<ShooterRow[]>(page, '/api/shooters');
  if (first === undefined) throw new Error('the seeded fixtures have no shooters');
  const shooter = await getJson<ShooterDetail>(page, `/api/shooters/${first.shooter_id}`);

  await page.goto(`/shooters/${first.shooter_id}`);
  const section = page.getByRole('region', { name: 'Shareable profile card' });
  await expect(section.getByRole('heading', { name: shooter.display_name })).toBeVisible();
  await expect(
    section.getByText(shooter.odometer.clays_broken.toLocaleString('en-US')),
  ).toBeVisible();
  const name = await download(page, section.getByRole('button', { name: 'Share image' }));
  expect(name).toBe(`sunday-clays-${slug(shooter.display_name)}.png`);
  await fitsTheScreen(page);
});

test('a Year in Review card downloads as an image', async ({ page }) => {
  const { years } = await getJson<{ years: number[] }>(page, '/api/yir/2000');
  const year = years[years.length - 1];
  await page.goto(`/yir/${year}`);
  const button = page.getByRole('button', { name: `Share image: ${year} at a glance` });
  await expect(button).toBeVisible();
  expect(await download(page, button)).toBe(`sunday-clays-${year}-at-a-glance.png`);
  await fitsTheScreen(page);
});

test('a trophy card downloads as an image', async ({ page }) => {
  const { trophies } = await getJson<{ trophies: Trophy[] }>(page, '/api/achievements');
  await page.goto('/achievements');
  const button = page.getByRole('button', { name: /^Share image: / }).first();
  await expect(button).toBeVisible();
  const name = await download(page, button);
  expect(trophies.map((t) => `sunday-clays-trophy-${slug(t.code)}.png`)).toContain(name);
  await fitsTheScreen(page);
});
