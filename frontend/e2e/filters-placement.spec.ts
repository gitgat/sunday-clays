import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import { expectNoSideScroll } from './layout';

/** Desktop: the filters sit in a header bar at the top of the content, not in the side nav. */
test('desktop: the round-type and time-window filters live in the content header', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'the content header only exists from 1024 px');
  await page.goto('/');
  const bar = page.getByRole('group', { name: 'Page filters' });
  await expect(bar).toBeVisible();
  await expect(bar.getByRole('button', { name: 'Round type' })).toBeVisible();
  await expect(bar.getByRole('group', { name: 'Time window' })).toBeVisible();
  // The bar is inside <main>, above the page, and the side nav holds only the name and the pages.
  await expect(page.getByRole('main').getByRole('group', { name: 'Page filters' })).toBeVisible();
  const side = page.getByRole('complementary');
  await expect(side.getByRole('link', { name: 'Sunday Clays' })).toBeVisible();
  await expect(side.getByRole('button', { name: 'Round type' })).toHaveCount(0);
  await expect(side.getByRole('group', { name: 'Time window' })).toHaveCount(0);
  const barBox = await bar.boundingBox();
  const h1Box = await page.getByRole('heading', { level: 1 }).first().boundingBox();
  expect(barBox).not.toBeNull();
  expect(h1Box).not.toBeNull();
  expect((barBox?.y ?? 0) + (barBox?.height ?? 0)).toBeLessThanOrEqual(h1Box?.y ?? 0);
  await expectNoSideScroll(page);
});

test('desktop: the filter bar stays at the top while the page scrolls', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'the content header only exists from 1024 px');
  await page.goto('/leaderboards?w=all&metric=avg_score');
  const bar = page.getByRole('group', { name: 'Page filters' });
  await expect(page.getByRole('table', { name: 'Leaderboard standings' })).toBeVisible();
  await page.evaluate(() => {
    window.scrollTo(0, document.documentElement.scrollHeight);
  });
  const box = await bar.boundingBox();
  expect(box?.y ?? 99).toBeLessThanOrEqual(1);
  await expectNoSideScroll(page);
});

/** Phone: the filters stay in the top bar and there is no content header. */
test('phone: the filters live in the top bar and no content header renders', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'the top bar only exists below 1024 px');
  await page.goto('/');
  const top = page.locator('header').first();
  await expect(top.getByRole('button', { name: 'Round type' })).toBeVisible();
  await expect(top.getByRole('combobox', { name: 'Time window' })).toBeVisible();
  await expect(page.getByRole('group', { name: 'Page filters' })).toHaveCount(0);
  await expectNoSideScroll(page);
});

/**
 * Each page shows only the filters it honours. Hidden filters keep their URL values, and a page that
 * honours neither shows no filter bar at all.
 */
async function shownFilters(page: Page, testInfo: { project: { name: string } }) {
  const scope =
    testInfo.project.name === 'mobile'
      ? page.locator('header').first()
      : page.getByRole('group', { name: 'Page filters' });
  return {
    scope,
    roundType: scope.getByRole('button', { name: 'Round type' }),
    window: scope
      .getByRole('group', { name: 'Time window' })
      .or(scope.getByRole('combobox', { name: 'Time window' })),
  };
}

test('Club shows both filters', async ({ page }, testInfo) => {
  await page.goto('/club');
  await expect(page.getByRole('heading', { level: 1, name: 'Club' })).toBeVisible();
  const shown = await shownFilters(page, testInfo);
  await expect(shown.roundType).toBeVisible();
  await expect(shown.window).toBeVisible();
  await expectNoSideScroll(page);
});

test('Leaderboards, Records and Race show both filters', async ({ page }, testInfo) => {
  for (const [path, title] of [
    ['/leaderboards?w=6m', 'Leaderboards'],
    ['/records?w=6m', 'Records'],
    ['/race?w=6m', 'Race'],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible();
    const shown = await shownFilters(page, testInfo);
    await expect(shown.roundType).toBeVisible();
    await expect(shown.window).toBeVisible();
    await expect(page).toHaveURL(/[?&]w=6m(&|$)/);
    await expectNoSideScroll(page);
  }
});

test('Trophies shows no filter bar at all', async ({ page }, testInfo) => {
  await page.goto('/achievements?rt=sporting&w=6m');
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
  const shown = await shownFilters(page, testInfo);
  await expect(shown.roundType).toHaveCount(0);
  await expect(shown.window).toHaveCount(0);
  if (testInfo.project.name !== 'mobile') await expect(shown.scope).toHaveCount(0);
  await expect(page).toHaveURL(/rt=sporting/);
  await expectNoSideScroll(page);
});
