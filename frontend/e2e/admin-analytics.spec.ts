import { randomUUID } from 'node:crypto';

import type { APIRequestContext, Page } from '@playwright/test';

import { ADMIN_STATE, VIEWER_STATE } from './authState';
import { expect, test } from './fixtures';
import { expectNoSideScroll, expectTapTargets, whenSettled } from './layout';

/**
 * Admin Analytics and the page-view beacon (Plan 16). Counts are read from the API before and
 * after, never hard-coded: both projects share one stack and run at once.
 */

type Kinds = { page_kind: string; views: number }[];
type Beacon = Record<string, unknown>;

async function views(request: APIRequestContext, kind: string): Promise<number> {
  const response = await request.get('/api/admin/analytics/pages'); // all time, to today
  expect(response.ok()).toBe(true);
  return ((await response.json()) as Kinds).find((k) => k.page_kind === kind)?.views ?? 0;
}

function recordBeacons(page: Page): Beacon[] {
  const sent: Beacon[] = [];
  page.on('request', (request) => {
    if (request.url().endsWith('/api/pageviews') && request.method() === 'POST') {
      sent.push(request.postDataJSON() as Beacon);
    }
  });
  return sent;
}

const beaconAnswered = (page: Page) =>
  page.waitForResponse(
    (r) => r.url().endsWith('/api/pageviews') && r.request().method() === 'POST',
  );

test.describe('as a viewer', () => {
  test('each page sends one beacon with only a kind, a state, a time and a random id', async ({
    page,
    playwright,
    baseURL,
  }) => {
    const device = randomUUID();
    await page.addInitScript((id) => {
      localStorage.setItem('sc.device', id);
    }, device);
    const admin = await playwright.request.newContext({ baseURL, storageState: ADMIN_STATE });
    const before = await views(admin, 'leaderboards');
    const sent = recordBeacons(page);

    const first = beaconAnswered(page);
    await page.goto('/leaderboards');
    expect((await first).status()).toBe(204);
    const second = beaconAnswered(page);
    await page.getByRole('link', { name: 'Home', exact: true }).first().click();
    expect((await second).status()).toBe(204);

    expect(sent.map((b) => b.page_kind)).toEqual(['leaderboards', 'home']);
    for (const body of sent) {
      expect(Object.keys(body).sort()).toEqual(['at', 'device_id', 'me_state', 'page_kind']);
      expect(body.device_id).toBe(device);
      expect(body.me_state).toMatch(/^(picked|skipped|none)$/);
      expect(JSON.stringify(body)).not.toContain('/');
    }
    await expect.poll(() => views(admin, 'leaderboards')).toBeGreaterThanOrEqual(before + 1);
    await admin.dispose();
  });
});

test.describe('as an admin', () => {
  test.use({ storageState: ADMIN_STATE });

  // With no counted view in the window, "Page views by page" and "Busiest days" are empty states
  // with no chart controls. A fresh stack, or this file running before any viewer page
  // (fullyParallel; auth.setup logs in through the API), may have none yet: store one first.
  // The kind is 'other', so the admin test's 'compare' count is untouched.
  test.beforeAll(async ({ playwright }, testInfo) => {
    const viewer = await playwright.request.newContext({
      baseURL: testInfo.project.use.baseURL,
      storageState: VIEWER_STATE,
    });
    const response = await viewer.post('/api/pageviews', {
      data: { device_id: randomUUID(), page_kind: 'other', me_state: 'none' },
    });
    expect(response.status()).toBe(204);
    // "Fist bumps per day" is an empty state with no controls until some insight has a bump.
    const feed = (await (await viewer.get('/api/insights/home')).json()) as {
      hero: { key: string } | null;
    };
    if (feed.hero === null) throw new Error('the fx world has a top insight');
    const bump = await viewer.post('/api/bumps', {
      data: { key: feed.hero.key, device_id: randomUUID() },
    });
    expect(bump.ok()).toBe(true);
    await viewer.dispose();
  });

  test('admin pages send no beacon, and the server drops one an admin sends anyway', async ({
    page,
  }) => {
    const sent = recordBeacons(page);
    await page.goto('/admin/analytics');
    await expect(page.getByRole('heading', { level: 1, name: 'Analytics' })).toBeVisible();
    // Not /leaderboards: its "Board as of" slider keeps a permanent status that never settles.
    await page.goto('/shooters');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await whenSettled(page);
    expect(sent).toEqual([]);
    // Nothing in the e2e suite opens /compare, so its count only moves if this beacon counts.
    const before = await views(page.request, 'compare');
    const response = await page.request.post('/api/pageviews', {
      data: { device_id: randomUUID(), page_kind: 'compare', me_state: 'none' },
    });
    expect(response.status()).toBe(204);
    expect(await views(page.request, 'compare')).toBe(before);
  });

  test('the Analytics page shows four charts, each with Table, CSV, fullscreen and an explainer', async ({
    page,
  }) => {
    await page.goto('/admin/analytics');
    await expect(page.getByRole('heading', { level: 1, name: 'Analytics' })).toBeVisible();
    await whenSettled(page);
    await expect(page.getByText(/^Last 8 weeks · /)).toBeVisible();
    for (const title of [
      'Visitors',
      'Page views by page',
      'Fist bumps per day',
      '“Which one are you?” answers',
    ]) {
      const card = page.getByRole('region', { name: title });
      await expect(card).toBeVisible();
      for (const name of ['Table', 'CSV', 'Fullscreen', 'About this chart']) {
        // The chart chunk is lazy: give it room on a slow runner.
        await expect(card.getByRole('button', { name })).toBeVisible({ timeout: 20_000 });
      }
    }
    await expect(page.getByRole('region', { name: 'Busiest days' })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Most-bumped insights' })).toBeVisible();
    await expect(
      page.getByRole('list', { name: 'Busiest days' }).getByRole('listitem').first(),
    ).toBeVisible();
    await whenSettled(page);
    await expectNoSideScroll(page);
    await expectTapTargets(page);
  });

  test('visitors switch to weeks, show a table, open fullscreen and download every day', async ({
    page,
  }) => {
    await page.goto('/admin/analytics');
    await whenSettled(page);
    const card = page.getByRole('region', { name: 'Visitors' });
    await expect(card.getByRole('button', { name: 'Per week' })).toBeVisible({ timeout: 20_000 });
    await card.getByRole('button', { name: 'About this chart' }).click();
    await expect(card.getByRole('heading', { name: 'What this shows' })).toBeVisible();
    await card.getByRole('button', { name: 'Per week' }).click();
    await card.getByRole('button', { name: 'Table' }).click();
    await expect(card.getByRole('columnheader', { name: 'Week of' })).toBeVisible();
    await card.getByRole('button', { name: 'Fullscreen' }).click();
    const dialog = page.getByRole('dialog', { name: 'Visitors' });
    await expect(dialog.getByText('Every week on record.')).toBeVisible();
    const download = page.waitForEvent('download');
    await dialog.getByRole('button', { name: 'CSV' }).click();
    expect((await download).suggestedFilename()).toMatch(/^visitors-week-\d{4}-\d{2}-\d{2}\.csv$/);
    await expectNoSideScroll(page);
  });

  test('Analytics is in the admin navigation', async ({ page }, testInfo) => {
    await page.goto('/admin/ops');
    if (testInfo.project.name === 'mobile') {
      await page.getByRole('button', { name: 'More' }).click();
      await page
        .getByRole('navigation', { name: 'More' })
        .getByRole('link', { name: 'Analytics' })
        .click();
    } else {
      await page.getByRole('complementary').getByRole('link', { name: 'Analytics' }).click();
    }
    await expect(page).toHaveURL(/\/admin\/analytics$/);
    await expect(page.getByRole('heading', { level: 1, name: 'Analytics' })).toBeVisible();
    await whenSettled(page);
  });
});
