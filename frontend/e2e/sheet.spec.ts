import { readFile } from 'node:fs/promises';

import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import {
  expectNoSideScroll,
  expectTapTargets,
  expectTitlesUntruncated,
  whenSettled,
} from './layout';
import { longDate } from './window';

/** The Sunday Sheet end to end (Plan 14). Expectations come from the API at run time. */

interface Chart {
  type: 'explorer' | 'page';
  route: string | null;
  anchor: string | null;
  window: { from: string; to: string };
  highlight: Record<string, unknown[] | null>;
}
interface Post {
  post_key: string;
  type: string;
  see_why: { kind: 'chart' | 'link'; label: string; chart?: Chart | null; href?: string | null };
}
interface Issue {
  masthead: { date: string; issue: number; previous: string | null; next: string | null };
  numbers: { shooters: number; median: number | null; top_score: number | null; trophies: number };
  posts: Post[];
  more: { posts: Post[] }[];
}

async function getJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), path).toBe(true);
  return (await response.json()) as T;
}

/** Sum of layout shifts not caused by input, from the page's first paint (CLS without windows). */
async function trackLayoutShift(page: Page): Promise<() => Promise<number>> {
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
  return () => page.evaluate(() => (window as unknown as { __shift: number }).__shift);
}

test('/ is the latest issue: masthead, the four numbers, and nothing jumps once it loads', async ({
  page,
}) => {
  const issue = await getJson<Issue>(page, '/api/sheet/latest');
  const shift = await trackLayoutShift(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'The Sunday Sheet' })).toBeVisible();
  await expect(
    page.getByText(`${longDate(issue.masthead.date)} · Issue ${String(issue.masthead.issue)}`),
  ).toBeVisible();
  const numbers = page.getByRole('region', { name: 'This Sunday in numbers' });
  await expect(numbers.getByText(String(issue.numbers.shooters), { exact: true })).toBeVisible();
  await expect(numbers.getByText(String(issue.numbers.trophies), { exact: true })).toBeVisible();
  await whenSettled(page);
  expect(await shift(), 'layout shift after load').toBeLessThan(0.05);
  await expectNoSideScroll(page);
  await expectTitlesUntruncated(page);
  await expectTapTargets(page);
});

test('nothing jumps for a returning shooter either', async ({ page }) => {
  const shooters = await getJson<{ shooter_id: number; display_name: string }[]>(
    page,
    '/api/shooters?q=Hadley',
  );
  const hadley = shooters.find((s) => s.display_name === 'Hadley, Ike');
  await page.addInitScript((id) => localStorage.setItem('sc.me', String(id)), hadley?.shooter_id);
  const shift = await trackLayoutShift(page);
  await page.goto('/');
  await expect(
    page.getByRole('region', { name: 'Your Sunday' }).getByText('Last out'),
  ).toBeVisible();
  await whenSettled(page);
  expect(await shift(), 'layout shift after load').toBeLessThan(0.05);
});

/** Top-left corner of the first element a locator finds, or null when it is absent. */
async function cornerOf(page: Page, selector: string): Promise<{ x: number; y: number } | null> {
  const box = await page.locator(selector).first().boundingBox();
  return box === null ? null : { x: box.x, y: box.y };
}

test('a phone stacks the blocks in Sheet order', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'the phone order is a 390 px layout');
  await page.goto('/');
  await whenSettled(page);
  const block = (name: string): string => `[data-sheet-block="${name}"]`;
  // The headline and the spotlight are both inside the lead block: find them by their card titles.
  const stack: [string, string][] = [
    ['masthead', block('masthead')],
    ['numbers', block('numbers')],
    ['Your Sunday', block('you')],
    ['headline', `${block('lead')} >> text=Top story`],
    ['spotlight', `${block('lead')} >> text=Spotlight`],
    ['feed', block('feed')],
    ['more', block('more')],
    ['next Sunday', block('next')],
    ['club pulse', block('pulse')],
    ['details', block('details')],
  ];
  const found: { name: string; y: number }[] = [];
  for (const [name, selector] of stack) {
    const corner = await cornerOf(page, selector);
    if (corner !== null) found.push({ name, y: corner.y });
  }
  const names = found.map((f) => f.name);
  expect(names).toEqual(
    expect.arrayContaining([
      'masthead',
      'numbers',
      'Your Sunday',
      'headline',
      'spotlight',
      'feed',
      'more',
      'next Sunday',
      'club pulse',
      'details',
    ]),
  );
  const ys = found.map((f) => f.y);
  expect(ys, `tops of ${names.join(', ')}`).toEqual([...ys].sort((a, b) => a - b));
  expect(new Set(ys).size, 'every block starts on its own row').toBe(ys.length);
  // One column: every block starts at the same left edge.
  const xs = new Set<number>();
  for (const [, selector] of stack) {
    const corner = await cornerOf(page, selector);
    if (corner !== null && selector.startsWith('[data-sheet-block') && !selector.includes('>>')) {
      xs.add(Math.round(corner.x));
    }
  }
  expect(xs.size, 'one column on a phone').toBe(1);
});

test('a desktop puts main on the left, Your Sunday and the rail on the right', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'the rail is a 1024 px and wider layout');
  await page.goto('/');
  await whenSettled(page);
  const box = async (selector: string) => {
    const found = await page.locator(selector).first().boundingBox();
    if (found === null) throw new Error(`${selector} is not on the page`);
    return found;
  };
  const main = await box('[data-sheet-column="main"]');
  const rail = await box('[data-sheet-column="rail"]');
  const you = await box('[data-sheet-block="you"]');
  const feed = await box('[data-sheet-block="feed"]');
  // Main takes the left two columns; Your Sunday and the rail share the right one.
  expect(rail.x).toBeGreaterThan(main.x + main.width - 1);
  expect(you.x).toBeCloseTo(rail.x, 0);
  expect(you.width).toBeCloseTo(rail.width, 0);
  expect(main.width).toBeGreaterThan(rail.width * 1.8);
  expect(feed.x).toBeLessThan(rail.x);
  // Your Sunday comes first, then the rail beneath it.
  expect(you.y).toBeLessThan(rail.y);
  expect(you.y + you.height).toBeLessThanOrEqual(rail.y + 1);
  expect(Math.abs(you.y - main.y), 'Your Sunday starts level with main').toBeLessThan(1);
});

test('with Your Sunday skipped the rail starts level with main', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'the rail is a 1024 px and wider layout');
  await page.addInitScript(() => {
    localStorage.setItem('sc.me.skip', '1');
  });
  await page.goto('/');
  await whenSettled(page);
  await expect(page.locator('[data-sheet-block="you"]')).toHaveCount(0);
  const main = await page.locator('[data-sheet-column="main"]').boundingBox();
  const rail = await page.locator('[data-sheet-column="rail"]').boundingBox();
  if (main === null || rail === null) throw new Error('main and the rail are on the page');
  expect(rail.x).toBeGreaterThan(main.x + main.width - 1);
  expect(Math.abs(rail.y - main.y), 'rail top vs main top').toBeLessThan(1);
});

test('tap targets are 44 px and nothing scrolls sideways, with a "me" set too', async ({
  page,
}) => {
  const shooters = await getJson<{ shooter_id: number; display_name: string }[]>(
    page,
    '/api/shooters?q=Hadley',
  );
  const hadley = shooters.find((s) => s.display_name === 'Hadley, Ike');
  await page.addInitScript((id) => localStorage.setItem('sc.me', String(id)), hadley?.shooter_id);
  await page.goto('/');
  await expect(
    page.getByRole('region', { name: 'Your Sunday' }).getByText('Last out'),
  ).toBeVisible();
  await whenSettled(page);
  await expectNoSideScroll(page);
  await expectTapTargets(page);
  await expectTitlesUntruncated(page);
});

test('every post offers "See why" and "Share image", and the masthead offers "Share this Sheet"', async ({
  page,
}) => {
  const issue = await getJson<Issue>(page, '/api/sheet/latest');
  await page.goto('/');
  await whenSettled(page);
  await expect(
    page.locator('[data-sheet-block="masthead"]').getByRole('button', { name: 'Share this Sheet' }),
  ).toBeVisible();
  // "More from this Sunday" is a closed <details>: its posts are in the page but not exposed to
  // role queries, so open it to check them like the rest.
  await page.locator('[data-sheet-block="more"] summary').click();
  const everyPost = [...issue.posts, ...issue.more.flatMap((group) => group.posts)];
  expect(everyPost.length).toBeGreaterThan(0);
  for (const post of everyPost) {
    const card = page.locator(`[data-post-key="${post.post_key}"]`);
    await expect(card.getByRole('link', { name: /^See why/ }), post.post_key).toHaveCount(1);
    await expect(card.getByRole('button', { name: 'Share image' }), post.post_key).toHaveCount(1);
  }
  // The feed posts are on screen: their buttons are visible, not just present.
  const first = issue.posts[0];
  if (first === undefined) throw new Error('the latest issue has posts');
  const card = page.locator(`[data-post-key="${first.post_key}"]`);
  await expect(card.getByRole('link', { name: /^See why/ })).toBeVisible();
  await expect(card.getByRole('button', { name: 'Share image' })).toBeVisible();
});

test('previous and next issue links walk the issues', async ({ page }) => {
  const latest = await getJson<Issue>(page, '/api/sheet/latest');
  const previous = latest.masthead.previous;
  if (previous === null) throw new Error('the fx world has more than one held Sunday');
  await page.goto('/');
  await page.getByRole('link', { name: '← Previous issue' }).click();
  await expect(page).toHaveURL(new RegExp(`/sheet/${previous}$`));
  await expect(
    page.getByText(`${longDate(previous)} · Issue ${String(latest.masthead.issue - 1)}`),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Next issue →' }).click();
  await expect(page).toHaveURL(new RegExp(`/sheet/${latest.masthead.date}$`));
  await expect(page.getByRole('link', { name: 'Next issue →' })).toHaveCount(0);
  await page.getByRole('link', { name: 'All issues' }).click();
  await expect(page).toHaveURL(/\/events$/);
});

test('a bump counts at once, survives a reload and can be taken back', async ({
  page,
}, testInfo) => {
  const issue = await getJson<Issue>(page, '/api/sheet/latest');
  // The two projects share one stack: each bumps its own post, so the counts never collide.
  const post = issue.posts[testInfo.project.name === 'mobile' ? 1 : 0];
  if (post === undefined) throw new Error('the latest issue has at least two posts');
  await page.goto('/');
  const button = page
    .locator(`[data-post-key="${post.post_key}"]`)
    .getByRole('button', { name: /^Fist bump/ });
  await expect(button).toHaveAttribute('aria-pressed', 'false');
  const before = Number(/(\d+)/.exec((await button.getAttribute('aria-label')) ?? '')?.[1]);
  await button.click();
  await expect(button).toHaveAttribute('aria-pressed', 'true');
  await expect(button).toHaveAccessibleName(new RegExp(`^Fist bump, ${String(before + 1)} bump`));
  await page.reload();
  await expect(button).toHaveAttribute('aria-pressed', 'true');
  await expect(button).toHaveAccessibleName(new RegExp(`^Fist bump, ${String(before + 1)} bump`));
  await button.click();
  await expect(button).toHaveAttribute('aria-pressed', 'false');
  await expect(button).toHaveAccessibleName(new RegExp(`^Fist bump, ${String(before)} bump`));
  await page.reload();
  await expect(button).toHaveAccessibleName(new RegExp(`^Fist bump, ${String(before)} bump`));
});

test('"See why" opens a post’s chart and rings the evidence', async ({ page }) => {
  const issue = await getJson<Issue>(page, '/api/sheet/latest');
  const post = issue.posts.find((p) => {
    const chart = p.see_why.chart;
    return (
      chart != null &&
      chart.type === 'page' &&
      (chart.route ?? '').startsWith('/shooters/') &&
      Object.values(chart.highlight).some((items) => (items ?? []).length > 0)
    );
  });
  if (post === undefined) throw new Error('the fx world has a feed post with a profile chart');
  const chart = post.see_why.chart as Chart;
  await page.goto('/');
  await page
    .locator(`[data-post-key="${post.post_key}"]`)
    .getByRole('link', { name: /^See why/ })
    .click();
  await expect(page).toHaveURL(new RegExp(`#chart-${chart.anchor ?? ''}$`));
  const target = page.locator(`#chart-${chart.anchor ?? ''}`);
  await expect(target).toBeVisible();
  const chip = target.locator('[data-marked]');
  await expect(chip).toContainText('Showing what the insight points to.');
  await expect(chip).not.toHaveAttribute('data-marked', '0');
  await whenSettled(page);
  await expectNoSideScroll(page);
});

test('Share on a post downloads its image on desktop', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'a phone hands the image to the share sheet');
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'share', { value: undefined, configurable: true });
    Object.defineProperty(navigator, 'canShare', { value: undefined, configurable: true });
  });
  const issue = await getJson<Issue>(page, '/api/sheet/latest');
  const post = issue.posts[0];
  if (post === undefined) throw new Error('the latest issue has posts');
  await page.goto('/');
  const pending = page.waitForEvent('download');
  await page
    .locator(`[data-post-key="${post.post_key}"]`)
    .getByRole('button', { name: 'Share image' })
    .click();
  const file = await pending;
  expect(file.suggestedFilename()).toMatch(
    new RegExp(`^sunday-sheet-${issue.masthead.date}-[a-z0-9-]+\\.png$`),
  );
  const bytes = await readFile(await file.path());
  expect([...bytes.subarray(0, 4)]).toEqual([0x89, 0x50, 0x4e, 0x47]);
});

test('"Which one are you?" fills Your Sunday, "Not me" asks again, and skip sticks', async ({
  page,
}) => {
  await page.goto('/');
  const ask = page.getByRole('region', { name: 'Which one are you?' });
  await ask.getByLabel('Your name').fill('Hadley');
  await ask.getByRole('button', { name: 'Hadley, Ike' }).click();
  const you = page.getByRole('region', { name: 'Your Sunday' });
  await expect(you.getByText('Last out')).toBeVisible();
  await you.getByRole('button', { name: 'Not me' }).click();
  await expect(ask).toBeVisible();
  await ask.getByRole('button', { name: 'Not a shooter / skip' }).click();
  await expect(ask).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('heading', { level: 1, name: 'The Sunday Sheet' })).toBeVisible();
  await whenSettled(page);
  await expect(page.getByRole('region', { name: 'Which one are you?' })).toHaveCount(0);
});
