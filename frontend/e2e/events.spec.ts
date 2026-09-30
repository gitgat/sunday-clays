import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

test('season page lists every 2026 event in the list and the calendar', async ({ page }) => {
  await page.goto('/events?year=2026');
  await expect(page.getByRole('heading', { level: 1, name: 'Sundays 2026' })).toBeVisible();
  await expect(
    page.getByRole('list', { name: 'Sundays in 2026' }).getByRole('listitem'),
  ).toHaveCount(36);
  await expect(
    page
      .getByRole('region', { name: 'Calendar 2026' })
      .getByRole('link', { name: /^Sep 13, 2026 — 13 shooters$/ }),
  ).toBeVisible();
});

test('event detail shows results, the station heatmap and the weather empty state', async ({
  page,
}) => {
  await page.goto('/events/2026-09-13');
  await expect(page.getByRole('heading', { level: 1, name: 'Sep 13, 2026' })).toBeVisible();
  await expect(page.getByText('Super Sporting', { exact: true })).toBeVisible();
  const results = page.getByRole('table', { name: 'Results' });
  await expect(results.getByRole('row')).toHaveCount(14);
  await expect(results.getByRole('link', { name: 'Hadley, Ike' })).toBeVisible();
  await expect(page.getByText('Station hits', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /csv/i }).first()).toBeVisible();
  await expect(page.getByText('No weather recorded for this Sunday')).toBeVisible();
});

test('tied winners share first place', async ({ page }) => {
  await page.goto('/events/2026-09-27');
  const results = page.getByRole('table', { name: 'Results' });
  await expect(results.getByRole('row', { name: /Stockton, Ethan/ })).toContainText('T1');
  await expect(results.getByRole('row', { name: /Finnegan, Stanton/ })).toContainText('T1');
});

test('attendance-only event shows the head count', async ({ page }) => {
  await page.goto('/events/2018-12-30');
  await expect(page.getByText('Attendance only — 7 shooters, no scores recorded')).toBeVisible();
  await expect(page.getByRole('table', { name: 'Results' })).toHaveCount(0);
});

/** C10: every link and button in the page body is at least 44 × 44 px. */
async function expectTapTargets(page: Page): Promise<void> {
  const small = await page
    .locator('main')
    .locator('a:visible, button:visible')
    .evaluateAll((elements) =>
      elements.flatMap((el) => {
        const { width, height } = el.getBoundingClientRect();
        const name = el.textContent?.trim() || el.getAttribute('aria-label');
        return width < 44 || height < 44
          ? [`${name}: ${Math.round(width)}×${Math.round(height)}`]
          : [];
      }),
    );
  expect(small, 'tap targets under 44 px').toEqual([]);
}

/** The page body's headings start at h1 and never skip a level. */
async function expectHeadingOutline(page: Page): Promise<void> {
  const levels = await page
    .locator('main')
    .locator('h1, h2, h3, h4, h5, h6')
    .evaluateAll((elements) => elements.map((el) => Number(el.tagName.slice(1))));
  expect(levels[0], `outline ${levels.join(' ')}`).toBe(1);
  expect(
    levels.filter((level, i) => i > 0 && level > (levels[i - 1] ?? 0) + 1),
    `outline ${levels.join(' ')}`,
  ).toEqual([]);
}

test('season page: 44 px targets, a calendar legend and an unbroken heading outline', async ({
  page,
}) => {
  await page.goto('/events?year=2026');
  await expect(page.getByRole('heading', { level: 1, name: 'Sundays 2026' })).toBeVisible();
  await expect(page.getByRole('list', { name: 'Calendar legend' })).toBeVisible();
  await expectTapTargets(page);
  await expectHeadingOutline(page);
});

test('event page: visibly underlined 44 px links and an unbroken heading outline', async ({
  page,
}) => {
  await page.goto('/events/2026-09-13');
  const hadley = page
    .getByRole('table', { name: 'Results' })
    .getByRole('link', { name: 'Hadley, Ike' });
  await expect(hadley).toHaveCSS('text-decoration-line', 'underline');
  await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible();
  await expectTapTargets(page);
  await expectHeadingOutline(page);
  for (const path of ['/events/2018-12-30', '/events/2026-09-20']) {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expectTapTargets(page);
    await expectHeadingOutline(page);
  }
});

test('a crafted date shows the not-found state', async ({ page }) => {
  for (const path of ['/events/0', '/events/abc', '/events/2026-02-30']) {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1, name: 'Sunday not found' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'calendar' })).toHaveAttribute('href', '/events');
  }
});

test('ECharts loads only for an event with station data', async ({ page }) => {
  const echarts: string[] = [];
  page.on('request', (request) => {
    if (/\/assets\/echarts-[^/]*\.js$/.test(request.url())) echarts.push(request.url());
  });
  await page.goto('/events/2026-09-27');
  await expect(page.getByRole('table', { name: 'Results' })).toBeVisible();
  await expect(page.getByText('Station hits', { exact: true })).toHaveCount(0);
  expect(echarts).toEqual([]);
  await page.goto('/events/2026-09-13');
  await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible();
  expect(echarts).toHaveLength(1);
});

test('an out-of-range season falls back to the nearest one', async ({ page }) => {
  await page.goto('/events?year=9999');
  await expect(page.getByRole('heading', { level: 1, name: 'Sundays 2026' })).toBeVisible();
  await page.goto('/events?year=-5');
  await expect(page.getByRole('heading', { level: 1, name: 'Sundays 2018' })).toBeVisible();
});

test('the season calendar explains itself and says the year arrows set its period', async ({
  page,
}) => {
  await page.goto('/events?year=2026');
  const region = page.getByRole('region', { name: 'Calendar 2026' });
  const about = region.getByRole('button', { name: 'About this chart' });
  await expect(about).toHaveAttribute('aria-expanded', 'false');
  await about.click();
  await expect(about).toHaveAttribute('aria-expanded', 'true');
  await expect(region.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  await expect(region.getByRole('heading', { name: "How it's worked out" })).toBeVisible();
  await expect(region.getByText('One year at a time')).toBeVisible();
  await expect(region.getByText('All time')).toHaveCount(0);
  await expectHeadingOutline(page);
  await expectNoSideScroll(page);
});

test('the station heatmap explains itself', async ({ page }) => {
  await page.goto('/events/2026-09-13');
  const region = page.getByRole('region', { name: 'Station hits' });
  const about = region.getByRole('button', { name: 'About this chart' });
  await about.click();
  await expect(region.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  await expect(region.getByRole('heading', { name: "How it's worked out" })).toBeVisible();
  await expectHeadingOutline(page);
});

test('an event page opens its explainers without a side scroll or a broken outline', async ({
  page,
}) => {
  await page.goto('/events/2026-09-13');
  await whenSettled(page);
  for (const name of [
    'About these results',
    'About Median',
    'About Difficulty',
    'About this comparison',
  ]) {
    const button = page.getByRole('button', { name });
    await button.scrollIntoViewIfNeeded();
    await button.click();
    await expect(button).toHaveAttribute('aria-expanded', 'true');
  }
  await expectHeadingOutline(page);
  await expectNoSideScroll(page);
});

test('the notables never include an upset, and the comparison is with the previous Sunday', async ({
  page,
}) => {
  const listed = await page.request.get('/api/events?year=2026');
  expect(listed.status()).toBe(200);
  const dates = ((await listed.json()) as { event_date: string; has_scores: boolean }[])
    .filter((e) => e.has_scores)
    .map((e) => e.event_date);
  for (const date of dates) {
    const detail = await page.request.get(`/api/events/${date}`);
    const kinds = ((await detail.json()) as { notables: { kind: string }[] }).notables.map(
      (n) => n.kind,
    );
    expect(
      kinds.filter((k) => k !== 'pb' && k !== 'first_timer'),
      date,
    ).toEqual([]);
  }
  await page.goto(`/events/${dates.at(-1)}`);
  await expect(page.getByRole('region', { name: 'vs previous Sunday' })).toBeVisible();
  await expect(page.getByText('vs last week')).toHaveCount(0);
  await expect(page.getByText(/upset/i)).toHaveCount(0);
});

test('a partial-results Sunday shows a dash, not 0.0, for the rating change', async ({ page }) => {
  const listed = await page.request.get('/api/events');
  const events = (await listed.json()) as {
    event_date: string;
    has_scores: boolean;
    results_complete: boolean;
  }[];
  const partial = events.find((e) => e.has_scores && !e.results_complete);
  test.skip(partial === undefined, 'no partial-results Sunday in the seeded data');
  await page.goto(`/events/${partial?.event_date}`);
  const results = page.getByRole('table', { name: 'Results' });
  await expect(results).toBeVisible();
  const last = await results
    .locator('tbody tr td:last-child')
    .evaluateAll((cells) => cells.map((c) => c.textContent?.trim()));
  expect(last.length).toBeGreaterThan(0);
  expect(new Set(last)).toEqual(new Set(['—']));
});

test('event page steps to the previous and next Sunday with scores', async ({ page }) => {
  const response = await page.request.get('/api/events?round_type=sporting');
  expect(response.ok()).toBe(true);
  const sundays = ((await response.json()) as { event_date: string; has_scores: boolean }[])
    .filter((e) => e.has_scores)
    .map((e) => e.event_date)
    .sort();
  const middle = Math.floor(sundays.length / 2);
  const [prev, here, next] = [sundays[middle - 1], sundays[middle], sundays[middle + 1]];
  if (!prev || !here || !next) throw new Error('the seeded fixtures need three scored Sundays');

  await page.goto(`/events/${here}?rt=sporting`);
  const nav = page.getByRole('navigation', { name: 'Other Sundays' });
  await expect(nav).toBeVisible();
  await expectNoSideScroll(page);
  await expectTapTargets(page);
  for (const link of await nav.getByRole('link').all()) {
    await expect(link).toHaveCSS('text-decoration-line', 'underline');
  }
  await expect(nav.getByRole('link', { name: /Previous Sunday/ })).toHaveAttribute(
    'href',
    `/events/${prev}?rt=sporting`,
  );
  await nav.getByRole('link', { name: /Next Sunday/ }).click();
  await expect(page).toHaveURL(new RegExp(`/events/${next}\\?rt=sporting`));
  await expect(page.getByRole('heading', { level: 1 })).toContainText(String(next.slice(0, 4)));
  await expect(page.getByRole('navigation', { name: 'Other Sundays' })).toBeVisible();
});
