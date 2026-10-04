import { readFile } from 'node:fs/promises';
import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

const CHART_TITLES = [
  'Club totals over time',
  'Attendance per Sunday',
  'Shooters and Sundays per year',
  'Seasonality',
  'Turnout vs weather',
  'Score distribution by year',
  'Median and top score',
  'Difficulty by Sunday',
  'Newcomers per year',
  'Newcomer retention',
  'First rounds',
  'Rounds by member status',
  'Guest → member conversion',
  'How open is the competition?',
];

test('club dashboard renders every chart with table and CSV controls', async ({ page }) => {
  const regularsResponse = page.waitForResponse('**/api/club/regulars*');
  await page.goto('/club');
  await expect(page.getByRole('heading', { level: 1, name: 'Club' })).toBeVisible();
  const regularsBody = await regularsResponse;
  for (const title of CHART_TITLES) {
    await expect(page.getByText(title, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByRole('button', { name: /csv/i })).toHaveCount(CHART_TITLES.length);
  // Regulars and lapsed use the server's today, so assert structure and read names from the API,
  // never hard-coded ones.
  const core = page.getByRole('region', { name: 'Core regulars' });
  const lapsed = page.getByRole('region', { name: 'Lapsed regulars' });
  await expect(core.getByRole('heading', { name: /^Core regulars \(\d+\)$/ })).toBeVisible();
  await expect(lapsed.getByRole('heading', { name: /^Lapsed regulars \(\d+\)$/ })).toBeVisible();
  const regulars = (await regularsBody.json()) as {
    core: { display_name: string }[];
    lapsed: { display_name: string }[];
  };
  for (const [panel, people] of [
    [core, regulars.core],
    [lapsed, regulars.lapsed],
  ] as const) {
    const [first] = people;
    if (first === undefined) await expect(panel).toContainText('None right now');
    else await expect(panel.getByRole('link', { name: first.display_name })).toBeVisible();
  }
  // First-class on both viewports: nothing may push the page sideways.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

interface Conversion {
  year: number;
  new_guests: number;
  converted: number;
}

test('every chart explains itself, with its window, and the page stays inside the screen', async ({
  page,
}) => {
  await page.goto('/club');
  await expect(page.getByRole('heading', { level: 1, name: 'Club' })).toBeVisible();
  // Time series follow the window; per-year and all-history charts say so.
  const tags: [string, string][] = [
    ['Attendance per Sunday', 'Last 8 weeks'],
    ['Difficulty by Sunday', 'Last 8 weeks'],
    ['Turnout vs weather', 'Last 8 weeks'],
    ['Seasonality', 'All time'],
    ['Guest → member conversion', 'All time'],
    ['How open is the competition?', 'All time'],
  ];
  for (const [title, tag] of tags) {
    const region = page.getByRole('region', { name: title, exact: true });
    await expect(region).toBeVisible({ timeout: 15_000 });
    const about = region.getByRole('button', { name: 'About this chart' });
    const box = await about.boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(44);
    await about.click();
    await expect(region.getByRole('heading', { name: 'What this shows' })).toBeVisible();
    await expect(region.getByRole('heading', { name: "How it's worked out" })).toBeVisible();
    // A windowed tag also names its dates ("Last 8 weeks · Aug 3 – Sep 27").
    await expect(
      region.getByText(tag === 'All time' ? tag : new RegExp(`^${tag} · `), {
        exact: tag === 'All time',
      }),
    ).toBeVisible();
  }
  const stat = page.getByRole('button', { name: 'About Sundays with full results' });
  await stat.click();
  await expect(page.getByText(/Sundays with only a head count/)).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test('guest conversion is a share of each year’s guests, never above 100%', async ({ page }) => {
  const response = await page.request.get('/api/club/conversion');
  expect(response.status()).toBe(200);
  const years = (await response.json()) as Conversion[];
  expect(years.length).toBeGreaterThan(0);
  for (const y of years) expect(y.converted, `${y.year}`).toBeLessThanOrEqual(y.new_guests);
  await page.goto('/club');
  const region = page.getByRole('region', { name: 'Guest → member conversion', exact: true });
  await region.getByRole('button', { name: 'Table' }).click({ timeout: 15_000 });
  const table = region.getByRole('table');
  await expect(table.getByRole('columnheader', { name: 'Joined %' })).toBeVisible();
  const pcts = await table
    .locator('tbody tr')
    .evaluateAll((rows) =>
      rows.map((row) => Number(row.querySelectorAll('td, th')[3]?.textContent ?? 'NaN')),
    );
  for (const [i, y] of years.entries()) {
    if (y.new_guests > 0) {
      expect(pcts[i], `${y.year}`).toBeCloseTo((100 * y.converted) / y.new_guests, 0);
    }
  }
});

test('the turnout card asks for the Sundays inside the window, anchored on the latest scored Sunday', async ({
  page,
}) => {
  const meta = (await (await page.request.get('/api/meta')).json()) as {
    last_score_date: string | null;
  };
  expect(meta.last_score_date).not.toBeNull();
  const windowed = page.waitForRequest(
    (r) => r.url().endsWith('/api/explore') && r.method() === 'POST',
  );
  await page.goto('/club');
  const filters = ((await windowed).postDataJSON() as { filters: Record<string, string | null> })
    .filters;
  expect(filters.date_to).toBe(meta.last_score_date);
  expect(filters.date_from).not.toBeNull();
  expect(String(filters.date_from) <= String(filters.date_to)).toBe(true);

  const all = page.waitForRequest((r) => r.url().endsWith('/api/explore') && r.method() === 'POST');
  await page.goto('/club?w=all');
  const allFilters = ((await all).postDataJSON() as { filters: Record<string, string | null> })
    .filters;
  expect(allFilters.date_from).toBeNull();
  expect(allFilters.date_to).toBe(meta.last_score_date);
});

test('fullscreen and the CSV cover every Sunday on record, not just the time window', async ({
  page,
}) => {
  // Counts come from the API at run time.
  const attendance = (await (await page.request.get('/api/club/attendance')).json()) as unknown[];
  expect(attendance.length).toBeGreaterThan(0);
  await page.goto('/club');

  // Attendance per Sunday: the card opens on the window, the CSV has every Sunday.
  const att = page.getByRole('region', { name: 'Attendance per Sunday', exact: true });
  const download = page.waitForEvent('download');
  await att.getByRole('button', { name: 'CSV' }).click({ timeout: 15_000 });
  const file = await download;
  const text = (await readFile(await file.path(), 'utf8')).replace(/^\uFEFF/, '');
  expect(text.trimEnd().split('\r\n')).toHaveLength(attendance.length + 1);

  // Turnout vs weather: fullscreen asks the Explorer for every Sunday, with no dates. The request
  // assertions below are the real guard: weather bands are bounded, so the row count cannot prove it.
  const turnout = page.getByRole('region', { name: 'Turnout vs weather', exact: true });
  await turnout.getByRole('button', { name: 'Table' }).click({ timeout: 15_000 });
  const inlineRows = await turnout.getByRole('row').count();
  await whenSettled(page);
  const full = page.waitForRequest(
    (r) =>
      r.url().endsWith('/api/explore') &&
      r.method() === 'POST' &&
      (r.postDataJSON() as { limit: number }).limit === 5000,
  );
  await page.setViewportSize({ width: 1440, height: 900 });
  await turnout.getByRole('button', { name: 'Fullscreen' }).click();
  const filters = ((await full).postDataJSON() as { filters: Record<string, string | null> })
    .filters;
  expect(filters.date_from).toBeNull();
  expect(filters.date_to).toBeNull();
  const dialog = page.getByRole('dialog', { name: 'Turnout vs weather' });
  await expect(dialog.getByRole('table')).toBeVisible();
  // Weather groups, not Sundays: the full set never has fewer groups than the window's.
  expect(await dialog.getByRole('row').count()).toBeGreaterThanOrEqual(inlineRows);
  await page.keyboard.press('Escape');

  // The same sheet at phone width stays inside the screen.
  await page.setViewportSize({ width: 390, height: 844 });
  await turnout.getByRole('button', { name: 'Fullscreen' }).click();
  await expect(dialog.getByRole('table')).toBeVisible();
  await expectNoSideScroll(page);
});
