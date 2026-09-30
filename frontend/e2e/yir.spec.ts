import type { Page } from '@playwright/test';
import { expect, test } from './fixtures';
import {
  expectNoSideScroll,
  expectTapTargets,
  expectTitlesUntruncated,
  whenSettled,
} from './layout';

const CHARTS = { timeout: 20_000 };

interface ClubYear {
  year: number;
  years: number[];
  totals: { rounds: number; scored_events: number };
  previous: { rounds: number } | null;
}

interface ShooterYear {
  display_name: string;
  totals: { events: number };
}

async function json<T>(page: Page, url: string): Promise<T> {
  const response = await page.request.get(url);
  expect(response.ok(), url).toBe(true);
  return (await response.json()) as T;
}

/** A past year with a previous year, found from the API rather than the clock or a fixed year. */
async function pickYear(page: Page): Promise<ClubYear> {
  const { years } = await json<ClubYear>(page, '/api/yir/2000');
  const candidates = await Promise.all(years.map((y) => json<ClubYear>(page, `/api/yir/${y}`)));
  const year = candidates.findLast((c) => c.previous !== null && c.totals.rounds > 0);
  if (year === undefined) throw new Error('the seeded fixtures have no two consecutive years');
  return year;
}

const int = (n: number): string => n.toLocaleString('en-US');

test('the club year matches the API, compares with the year before and fits the screen', async ({
  page,
}) => {
  const year = await pickYear(page);
  const previous = year.previous?.rounds ?? 0;
  await page.goto(`/yir/${year.year}`);
  await expect(
    page.getByRole('heading', { level: 1, name: `Year in Review ${year.year}` }),
  ).toBeVisible();
  const glance = page.getByRole('region', { name: `${year.year} at a glance` });
  const diff = year.totals.rounds - previous;
  const sign = diff > 0 ? '+' : diff < 0 ? '−' : '±';
  await expect(
    glance.getByText(
      `${int(year.totals.rounds)} (${sign}${int(Math.abs(diff))} vs ${year.year - 1})`,
    ),
  ).toBeVisible();
  const picker = page.getByRole('navigation', { name: 'Other years' });
  await expect(picker.getByRole('link', { name: String(year.year) })).toHaveAttribute(
    'aria-current',
    'page',
  );
  const months = page.getByRole('region', { name: 'Month by month' });
  await expect(months.getByRole('button', { name: 'Table' })).toBeVisible(CHARTS);
  await expect(months.getByRole('button', { name: 'CSV' })).toBeVisible();
  await expect(months.getByRole('button', { name: 'About this chart' })).toBeVisible();
  await expect(page.getByRole('list', { name: 'Most Sundays' })).toBeVisible(CHARTS);
  await whenSettled(page);
  await expectNoSideScroll(page);
  await expectTitlesUntruncated(page);
  await expectTapTargets(page);
});

test("a leader's year opens from the club year and matches the API", async ({ page }) => {
  const year = await pickYear(page);
  await page.goto(`/yir/${year.year}`);
  const leader = page.getByRole('list', { name: 'Most Sundays' }).getByRole('link').first();
  await expect(leader).toBeVisible(CHARTS);
  const href = await leader.getAttribute('href');
  expect(href).toMatch(new RegExp(`^/yir/${year.year}/shooters/\\d+`));
  await leader.click();
  const id = (href ?? '').split('/').pop() ?? '';
  const shooter = await json<ShooterYear>(page, `/api/yir/${year.year}/shooters/${id}`);
  const card = page.getByRole('region', { name: `${shooter.display_name}: ${year.year}` });
  await expect(card).toBeVisible();
  await expect(card.getByText(new RegExp(`^${shooter.totals.events}\\b`)).first()).toBeVisible();
  await expect(page.getByRole('link', { name: `Back to the club's ${year.year}` })).toBeVisible();
  await whenSettled(page);
  await expectNoSideScroll(page);
  await expectTitlesUntruncated(page);
});

test('home shows On this day', async ({ page }) => {
  await page.goto('/');
  const card = page.getByRole('region', { name: 'On this day' });
  await expect(card.getByRole('heading', { name: 'On this day' })).toBeVisible();
  // Which Sundays appear depends on today's date, so only the loaded state is checked.
  await expect(card.getByText(/years? ago|No Sunday near this date/).first()).toBeVisible();
  await expectNoSideScroll(page);
});
