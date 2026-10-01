import type { Page } from '@playwright/test';

import { VIEWER_STATE } from './authState';
import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

/** Fist bumps on insights and "Which one are you?" (Plan 15). Expectations come from the API. */

interface Insight {
  key: string;
}
interface Feed {
  as_of: string | null;
  hero: Insight | null;
  top: Insight[];
}
type Counts = Record<string, { bumps: number; bumped: boolean }>;

async function getJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), path).toBe(true);
  return (await response.json()) as T;
}

const bumpOf = (page: Page, key: string) =>
  page
    .locator(`[data-insight-key="${key}"]`)
    .first()
    .getByRole('button', { name: /^Fist bump/ });

const named = (count: number) => new RegExp(`^Fist bump, ${String(count)} bump`);

const countsLoaded = (page: Page, key?: string) =>
  page.waitForResponse(
    (r) =>
      r.url().includes('/api/bumps?') &&
      r.request().method() === 'GET' &&
      r.ok() &&
      (key === undefined || decodeURIComponent(r.url()).includes(key)),
  );

test('a bump counts at once, survives a reload and can be taken back', async ({
  page,
  playwright,
  baseURL,
}, testInfo) => {
  const feed = await getJson<Feed>(page, '/api/insights/home');
  // The two projects share one stack: each bumps its own insight, so the counts never collide.
  const insight = testInfo.project.name === 'mobile' ? feed.top[0] : feed.hero;
  if (insight == null) throw new Error('the fx world has a top story and a top insight');
  const sent = (method: 'POST' | 'DELETE') =>
    page.waitForResponse(
      (r) => r.url().endsWith('/api/bumps') && r.request().method() === method && r.ok(),
    );
  const button = bumpOf(page, insight.key);
  let device: string | null = null;
  try {
    let loaded = countsLoaded(page, insight.key);
    await page.goto('/');
    const first = (await (await loaded).json()) as Counts;
    device = await page.evaluate(() => localStorage.getItem('sc.device'));
    const before = first[insight.key]?.bumps ?? Number.NaN;
    // Polls until React has rendered the server's count.
    await expect(button).toHaveAccessibleName(named(before));
    await expect(button).toHaveAttribute('aria-pressed', 'false');
    await Promise.all([sent('POST'), button.click()]);
    await expect(button).toHaveAttribute('aria-pressed', 'true');
    await expect(button).toHaveAccessibleName(named(before + 1));
    loaded = countsLoaded(page, insight.key);
    await page.reload();
    const reloaded = (await (await loaded).json()) as Counts;
    expect(reloaded[insight.key]).toEqual({ bumps: before + 1, bumped: true });
    await expect(button).toHaveAttribute('aria-pressed', 'true');
    await expect(button).toHaveAccessibleName(named(before + 1));
    await Promise.all([sent('DELETE'), button.click()]);
    await expect(button).toHaveAttribute('aria-pressed', 'false');
    await expect(button).toHaveAccessibleName(named(before));
    loaded = countsLoaded(page, insight.key);
    await page.reload();
    const last = (await (await loaded).json()) as Counts;
    expect(last[insight.key]).toEqual({ bumps: before, bumped: false });
    await expect(button).toHaveAccessibleName(named(before));
  } finally {
    // A failed attempt must not leave a bump on the shared stack.
    if (device !== null) {
      // A fresh context: at a test timeout the page's own is already closed.
      const cleanup = await playwright.request.newContext({ baseURL, storageState: VIEWER_STATE });
      await cleanup
        .delete('/api/bumps', { data: { key: insight.key, device_id: device } })
        .catch(() => undefined);
      await cleanup.dispose();
    }
  }
});

test('every insight list offers a bump: Home, a profile and a Sunday', async ({ page }) => {
  const home = await getJson<Feed>(page, '/api/insights/home');
  const shooters = await getJson<{ shooter_id: number; display_name: string }[]>(
    page,
    '/api/shooters?q=Hadley',
  );
  const hadley = shooters.find((s) => s.display_name === 'Hadley, Ike');
  if (hadley === undefined) throw new Error('the fx world has Hadley, Ike');
  const profile = await getJson<Feed>(page, `/api/insights/shooters/${String(hadley.shooter_id)}`);
  if (home.as_of === null) throw new Error('the fx world has a latest Sunday');
  const sunday = await getJson<Feed>(page, `/api/insights/sundays/${home.as_of}`);
  const pages: [string, Insight | undefined][] = [
    ['/', home.top[0]],
    [`/shooters/${String(hadley.shooter_id)}`, profile.top[0]],
    [`/events/${home.as_of}`, sunday.top[0]],
  ];
  expect(pages.length).toBeGreaterThan(0);
  for (const [path, insight] of pages) {
    if (insight === undefined) throw new Error(`${path} has a top insight in the fx world`);
    await page.goto(path);
    const button = bumpOf(page, insight.key);
    await expect(button, path).toBeVisible();
    const box = await button.boundingBox();
    expect(box?.height ?? 0, `${path} bump height`).toBeGreaterThanOrEqual(44);
    expect(box?.width ?? 0, `${path} bump width`).toBeGreaterThanOrEqual(44);
    await whenSettled(page);
    await expectNoSideScroll(page);
  }
});

test('bump counts arriving never move the page', async ({ page }) => {
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/api/bumps?**', async (route) => {
    await held;
    await route.continue();
  });
  await page.addInitScript(() => {
    const w = window as unknown as { __shift: number };
    w.__shift = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as (PerformanceEntry & {
        value: number;
        hadRecentInput: boolean;
      })[]) {
        if (!entry.hadRecentInput) w.__shift += entry.value;
      }
    }).observe({ type: 'layout-shift', buffered: true });
  });
  await page.goto('/');
  await expect(
    page
      .locator('[data-insight-key]')
      .first()
      .getByRole('button', { name: /^Fist bump/ }),
  ).toBeVisible();
  await whenSettled(page);
  // Measure only what the counts do once they land.
  await page.evaluate(() => {
    (window as unknown as { __shift: number }).__shift = 0;
  });
  const loaded = countsLoaded(page);
  release();
  await loaded;
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
  );
  const shift = await page.evaluate(() => (window as unknown as { __shift: number }).__shift);
  expect(shift, 'layout shift from bump counts').toBeLessThan(0.01);
});

test('"Which one are you?": a pick fills the panel, "Not me" asks again, a skip stays away', async ({
  page,
}) => {
  await page.goto('/');
  const personal = page.getByRole('complementary', { name: 'Personal' });
  const question = personal.getByRole('heading', { name: 'Which one are you?' });
  await expect(question).toBeVisible();
  await personal.getByLabel('Your name').fill('Hadley');
  await personal
    .getByRole('list', { name: 'Matching shooters' })
    .getByRole('button', { name: 'Hadley, Ike' })
    .click();
  await expect(personal.getByText('Last out')).toBeVisible();
  await expect(personal.getByRole('heading', { name: 'Your panel' })).toBeFocused();
  await page.reload();
  await expect(personal.getByText('Last out')).toBeVisible();
  await personal.getByRole('button', { name: 'Not me' }).click();
  await expect(question).toBeVisible();
  await expect(question).toBeFocused();
  expect(await page.evaluate(() => localStorage.getItem('sc.me'))).toBeNull();
  await personal.getByRole('button', { name: /^Skip, I.m not a shooter$/ }).click();
  await expect(question).toHaveCount(0);
  await expect(personal.getByText(/tap “That’s me”/)).toBeVisible();
  await page.reload();
  await expect(personal.getByRole('heading', { name: 'Your panel' })).toBeVisible();
  await expect(question).toHaveCount(0);
  await expectNoSideScroll(page);
});
