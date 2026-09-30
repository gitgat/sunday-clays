import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import { expectNoSideScroll } from './layout';

/** Every expectation comes from the API at run time: no wall clock, no hard-coded names or dates. */

interface Board {
  event_dates: string[];
  rows: { rank: number; shooter_id: number; display_name: string; value: number }[];
}

async function board(page: Page, query: string): Promise<Board> {
  const response = await page.request.get(`/api/leaderboards?${query}`);
  expect(response.status()).toBe(200);
  return (await response.json()) as Board;
}

async function scoredDates(page: Page): Promise<string[]> {
  return (await board(page, 'metric=wins')).event_dates;
}

/** Same wording as lib/format.ts formatDate, computed here from the ISO date. */
function shortDate(iso: string): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

test('phone: a custom time window from the top bar select, kept while navigating', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'the top-bar select only exists below 1024 px');
  await page.setViewportSize({ width: 390, height: 844 });
  const dates = await scoredDates(page);
  const start = dates.at(-6);
  const end = dates.at(-2);
  if (start === undefined || end === undefined) throw new Error('need six scored Sundays');

  await page.goto('/club');
  await page.getByRole('combobox', { name: 'Time window' }).selectOption('custom');
  const sheet = page.getByRole('dialog', { name: 'Custom dates' });
  await expect(sheet).toBeVisible();
  // A bottom sheet on a phone, with 44 px inputs and buttons that fit the screen.
  const box = await sheet.boundingBox();
  expect(box?.y ?? 0).toBeGreaterThan(300);
  await sheet.getByLabel('Start date').fill(start);
  await sheet.getByLabel('End date').fill(end);
  for (const control of [
    sheet.getByLabel('Start date'),
    sheet.getByLabel('End date'),
    sheet.getByRole('button', { name: 'Apply' }),
    sheet.getByRole('button', { name: 'Cancel' }),
  ]) {
    expect((await control.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await sheet.getByRole('button', { name: 'Apply' }).click();
  await expect(sheet).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`[?&]w=${start}\\.\\.${end}(&|$)`));

  // A windowed chart names the dates it covers.
  await expect(
    page.getByText(`${shortDate(start)} – ${shortDate(end)}`, { exact: true }).first(),
  ).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);

  // In-app navigation keeps it: Home is a tab, Club sits in More.
  await page.getByRole('navigation', { name: 'Tabs' }).getByRole('link', { name: 'Home' }).click();
  await expect(page).toHaveURL(new RegExp(`w=${start}\\.\\.${end}`));
  await page
    .getByRole('navigation', { name: 'Tabs' })
    .getByRole('button', { name: 'More' })
    .click();
  await page.getByRole('navigation', { name: 'More' }).getByRole('link', { name: 'Club' }).click();
  await expect(page).toHaveURL(/\/club/);
  await expect(page).toHaveURL(new RegExp(`w=${start}\\.\\.${end}`));
  await expectNoSideScroll(page);
});

test('desktop: the Custom button in the filter bar opens a centred sheet', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'the filter bar button only exists from 1024 px');
  const dates = await scoredDates(page);
  const start = dates.at(-6);
  const end = dates.at(-2);
  if (start === undefined || end === undefined) throw new Error('need six scored Sundays');

  await page.goto('/club');
  await page
    .getByRole('group', { name: 'Time window' })
    .getByRole('button', { name: 'Custom' })
    .click();
  const sheet = page.getByRole('dialog', { name: 'Custom dates' });
  await expect(sheet).toBeVisible();
  const box = await sheet.boundingBox();
  const viewport = page.viewportSize();
  const centre = (box?.x ?? 0) + (box?.width ?? 0) / 2;
  expect(Math.abs(centre - (viewport?.width ?? 0) / 2)).toBeLessThan(2);
  expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThan(viewport?.height ?? 0);
  await sheet.getByLabel('Start date').fill(start);
  await sheet.getByLabel('End date').fill(end);
  await sheet.getByRole('button', { name: 'Apply' }).click();
  await expect(page).toHaveURL(new RegExp(`[?&]w=${start}\\.\\.${end}(&|$)`));
  await expect(
    page.getByRole('group', { name: 'Time window' }).getByRole('button', { name: 'Custom' }),
  ).toHaveAttribute('aria-pressed', 'true');
  await expect(
    page.getByText(`${shortDate(start)} – ${shortDate(end)}`, { exact: true }).first(),
  ).toBeVisible();
  await expectNoSideScroll(page);
});
