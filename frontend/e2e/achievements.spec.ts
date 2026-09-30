import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';

interface Trophy {
  code: string;
  name: string;
  category: string;
  holders: number;
}
interface AchievementsBody {
  trophies: Trophy[];
  recent: { event_date: string }[];
  recent_total: number;
}
interface DetailBody {
  trophy: Trophy;
  holders: { shooter_id: number }[];
}

// Expectations come from the API at run time, never from hard-coded fixture values.
async function getJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), path).toBe(true);
  return (await response.json()) as T;
}

async function expectNoSideScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(overflow.scroll, 'page scrollWidth').toBeLessThanOrEqual(overflow.client);
}

/** Every underlined link and every button inside `root` is at least 44 px tall. */
async function expectTapTargets(page: Page, root: string): Promise<void> {
  const small = await page
    .locator(root)
    .locator('a:visible, button:visible')
    .evaluateAll((elements) =>
      elements.flatMap((el) => {
        const { width, height } = el.getBoundingClientRect();
        const name = el.textContent?.trim() || el.getAttribute('aria-label');
        return width < 44 || height < 44
          ? [`${name ?? ''}: ${Math.round(width)}×${Math.round(height)}`]
          : [];
      }),
    );
  expect(small, 'tap targets under 44 px').toEqual([]);
}

const trophyLink = (page: Page, code: string) =>
  page.locator(`a[href^="/achievements/${encodeURIComponent(code)}"]`).first();

test('Trophy Room lists trophies and filters by category', async ({ page }) => {
  const body = await getJson<AchievementsBody>(page, '/api/achievements');
  const inCategory = body.trophies.find((t) => t.category === 'competition');
  const outside = body.trophies.find((t) => t.category !== 'competition');
  if (!inCategory || !outside)
    throw new Error('the seeded fixtures need trophies in two categories');

  await page.goto('/achievements');
  await expect(page.getByRole('heading', { level: 1, name: 'Trophy Room' })).toBeVisible();
  const list = page.getByRole('region', { name: 'Trophies' });
  await expect(trophyLink(page, outside.code)).toBeVisible();
  await expect(list.getByRole('listitem')).toHaveCount(body.trophies.length);
  const about = page
    .getByRole('region', { name: 'Rarity' })
    .getByRole('button', { name: 'About this chart' });
  await about.click();
  await expect(page.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  await about.click();
  await expectNoSideScroll(page);
  await expectTapTargets(page, 'section[aria-label="Trophies"]');
  await expectTapTargets(page, 'section[aria-labelledby="recent-unlocks"]');

  await page.getByRole('button', { name: 'Competition' }).click();
  await expect(page).toHaveURL(/cat=competition/);
  await expect(trophyLink(page, inCategory.code)).toBeVisible();
  await expect(
    list.locator(`a[href^="/achievements/${encodeURIComponent(outside.code)}"]`),
  ).toHaveCount(0);
  await expect(list.getByRole('listitem')).toHaveCount(
    body.trophies.filter((t) => t.category === 'competition').length,
  );
});

test('trophy page lists every holder (Show all past 10)', async ({ page }) => {
  const { trophies } = await getJson<AchievementsBody>(page, '/api/achievements');
  const held = trophies.find((t) => t.holders > 0);
  if (!held) throw new Error('the seeded fixtures have no earned trophy');
  const detail = await getJson<DetailBody>(
    page,
    `/api/achievements/${encodeURIComponent(held.code)}`,
  );

  await page.goto(`/achievements/${encodeURIComponent(held.code)}`);
  await expect(page.getByRole('heading', { level: 1, name: held.name })).toBeVisible();
  const holders = page.getByRole('list', { name: 'Holders' });
  await expect(holders.getByRole('listitem')).toHaveCount(Math.min(10, detail.holders.length));
  if (detail.holders.length > 10) {
    await page.getByRole('button', { name: `Show all ${detail.holders.length} holders` }).click();
  }
  await expect(holders.getByRole('listitem')).toHaveCount(detail.holders.length);
  const holdersChart = page.getByRole('region', { name: 'Holders over time' });
  await expect(holdersChart).toBeVisible();
  await holdersChart.getByRole('button', { name: 'About this chart' }).click();
  await expect(page.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  await expectNoSideScroll(page);
  await expectTapTargets(page, 'ul[aria-label="Holders"]');
});

test('a holder profile shows the Trophy Case', async ({ page }) => {
  const { trophies } = await getJson<AchievementsBody>(page, '/api/achievements');
  const held = trophies.find((t) => t.holders > 0);
  if (!held) throw new Error('the seeded fixtures have no earned trophy');
  const detail = await getJson<DetailBody>(
    page,
    `/api/achievements/${encodeURIComponent(held.code)}`,
  );
  const [holder] = detail.holders;
  if (!holder) throw new Error('the earned trophy has no holder');

  await page.goto(`/shooters/${holder.shooter_id}`);
  const trophyCase = page.getByRole('region', { name: 'Trophy case for this shooter' });
  await expect(trophyCase.getByRole('heading', { name: 'Earned trophies' })).toBeVisible();
  await expect(trophyCase.getByText(held.name).first()).toBeVisible();
  await expect(trophyCase.getByRole('region', { name: 'Trophy timeline' })).toBeVisible();
  await expectNoSideScroll(page);
});

test('the event page shows trophies earned that day', async ({ page }) => {
  const { recent } = await getJson<AchievementsBody>(page, '/api/achievements');
  const [latest] = recent;
  if (!latest) throw new Error('the seeded fixtures have no recent unlock');

  await page.goto(`/events/${latest.event_date}`);
  await expect(page.getByRole('list', { name: 'Trophies earned today' })).toBeVisible();
  await expectNoSideScroll(page);
  await expectTapTargets(page, 'ul[aria-label="Trophies earned today"]');
});

test('Trophy Room recent unlocks show 10, then Show all', async ({ page }) => {
  const { recent, recent_total } = await getJson<AchievementsBody>(page, '/api/achievements');
  await page.goto('/achievements');
  const region = page.getByRole('region', { name: 'Recent unlocks' });
  await expect(region.getByRole('listitem')).toHaveCount(Math.min(10, recent.length));
  if (recent.length > 10) {
    await expectTapTargets(page, 'section[aria-labelledby="recent-unlocks"]');
    // A capped list (the server holds the latest 200) offers "the latest N", not "all".
    const lead = recent_total > recent.length ? 'Show the latest' : 'Show all';
    await region.getByRole('button', { name: `${lead} ${recent.length} unlocks` }).click();
    await expect(region.getByRole('listitem')).toHaveCount(recent.length);
    await expect(region.getByRole('button', { name: /Show (all|the latest)/ })).toHaveCount(0);
  } else {
    await expect(region.getByRole('button', { name: /Show all/ })).toHaveCount(0);
  }
  // Dates read "Sep 13, 2026", never ISO.
  await expect(region.locator('time').first()).not.toHaveText(/^\d{4}-\d{2}-\d{2}$/);
  await expectNoSideScroll(page);
});
