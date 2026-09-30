import { readFile } from 'node:fs/promises';
import type { Page } from '@playwright/test';
import { VIEWER_STATE } from './authState';
import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';
import { thinCount } from './thinCount';

// Signed in as a viewer; the fixtures were seeded once by auth.setup.ts (Plan 04 T2).
test.use({ storageState: VIEWER_STATE });

// The first query after the seed builds the API's per-data_version Explorer frames: about 1 s
// alone, but every parallel worker misses the cold cache at once and builds its own copy
// (8 concurrent cold requests took ~11.5 s locally), so the first result gets longer than 5 s.
const FIRST_RESULT = { timeout: 20_000 };

test('rounds by year come from the seeded fixtures', async ({ page }) => {
  await page.goto('/explorer?m=rounds&g=year&w=all');
  await expect(page.getByRole('img', { name: 'Rounds by year' })).toBeVisible(FIRST_RESULT);
  await expect(page.getByText('Based on 7,480 rounds')).toBeVisible();
  await page.getByRole('button', { name: 'Table' }).click();
  const table = page.getByRole('table', { name: 'Rounds by year' });
  await expect(table.getByRole('row')).toHaveCount(8);
  await expect(table.getByRole('row', { name: /^2020 843 843$/ })).toBeVisible();
  await expect(table.getByRole('row', { name: /^2025 1267 1267$/ })).toBeVisible();
  await expect(page).toHaveURL(/v=table/);
});

test('the query lives in the URL and survives a reload', async ({ page }) => {
  await page.goto('/explorer?w=all');
  await expect(page.getByRole('img', { name: 'Avg score by year' })).toBeVisible(FIRST_RESULT);
  await page.getByLabel('Metric').selectOption('rounds');
  await page.getByLabel('Group by').selectOption('gauge');
  await expect(page).toHaveURL(/m=rounds/);
  await expect(page).toHaveURL(/g=gauge/);
  await page.reload();
  await expect(page.getByLabel('Metric')).toHaveValue('rounds');
  await expect(page.getByLabel('Group by')).toHaveValue('gauge');
  await page.getByRole('button', { name: 'Table' }).click();
  await expect(
    page
      .getByRole('table', { name: 'Rounds by gauge' })
      .getByRole('row', { name: /^unspecified 7302 7302$/ }),
  ).toBeVisible();
});

test('the CSV export matches the query', async ({ page }) => {
  await page.goto('/explorer?m=rounds&g=year&w=all');
  await expect(page.getByRole('img', { name: 'Rounds by year' })).toBeVisible(FIRST_RESULT);
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'CSV' }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe('explorer-rounds-by-year.csv');
  const text = (await readFile(await file.path(), 'utf8')).replace(/^\uFEFF/, '');
  expect(text.split('\r\n').slice(0, 2)).toEqual(['Year,Rounds,n', '2020,843,843']);
});

test('an invalid combination explains itself instead of breaking the page', async ({ page }) => {
  await page.goto('/explorer?m=score&g=station');
  await expect(page.getByRole('heading', { name: "This query can't run" })).toBeVisible(
    FIRST_RESULT,
  );
  await expect(page.getByText('Grouping by station needs the Hit % metric')).toBeVisible();
});

test('the result follows the time window, explains itself and offers no Class', async ({
  page,
}) => {
  const meta = (await (await page.request.get('/api/meta')).json()) as {
    last_score_date: string;
  };
  const summary = (await (await page.request.get('/api/club/summary')).json()) as {
    n_rounds: number;
  };
  const windowed = page.waitForRequest(
    (r) => r.url().endsWith('/api/explore') && r.method() === 'POST',
  );
  await page.goto('/explorer?m=rounds&g=year');
  const filters = ((await windowed).postDataJSON() as { filters: Record<string, string | null> })
    .filters;
  expect(filters.date_to).toBe(meta.last_score_date);
  expect(filters.date_from).not.toBeNull();
  const region = page.getByRole('region', { name: 'Rounds by year', exact: true });
  await expect(region).toBeVisible(FIRST_RESULT);
  const based = await region.getByText(/^Based on [\d,]+ rounds$/).textContent();
  const n = Number(/Based on ([\d,]+)/.exec(based ?? '')?.[1]?.replaceAll(',', ''));
  expect(n).toBeGreaterThan(0);
  expect(n).toBeLessThanOrEqual(summary.n_rounds);

  const about = region.getByRole('button', { name: 'About this chart' });
  expect((await about.boundingBox())?.height).toBeGreaterThanOrEqual(44);
  await about.click();
  await expect(region.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  await expect(region.getByText(/^Last 8 weeks · /).first()).toBeVisible();

  // Classes are gone; the residual metric reads "Vs expected"; Sunday, not event.
  const groupBy = page.getByLabel('Group by');
  await expect(groupBy.getByRole('option', { name: 'Class' })).toHaveCount(0);
  await expect(groupBy.getByRole('option', { name: 'Sunday' })).toHaveCount(1);
  await expect(page.getByLabel('Metric').getByRole('option', { name: 'Vs expected' })).toHaveCount(
    1,
  );
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test('an insight link draws the dashed line and "Stop comparing" removes it', async ({ page }) => {
  await page.goto('/explorer?m=score&a=avg&g=year&w=all&cmp.m=adjusted');
  await expect(page.getByRole('img', { name: 'Avg score by year' })).toBeVisible(FIRST_RESULT);
  const stop = page.getByRole('button', { name: 'Stop comparing' });
  await expect(stop).toBeVisible(FIRST_RESULT);
  await expect(page.getByText('Dashed line: everyone')).toBeVisible();
  const box = await stop.boundingBox();
  expect(box?.height).toBeGreaterThanOrEqual(44);
  expect(box?.width).toBeGreaterThanOrEqual(44);
  await whenSettled(page);
  await expectNoSideScroll(page);
  await stop.click();
  await expect(page).not.toHaveURL(/cmp\./);
  await expect(stop).toHaveCount(0);
});

test('how the day played is a Sunday total with no round count', async ({ page }) => {
  await page.goto('/explorer?m=difficulty&g=event&w=all');
  await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible(FIRST_RESULT);
  await expect(page.getByText(/Based on/)).toHaveCount(0);
  await expectNoSideScroll(page);
});

test('fullscreen and the CSV cover every Sunday and every row, not just the window', async ({
  page,
}) => {
  const bodies: { limit: number; filters: Record<string, unknown> }[] = [];
  page.on('request', (r) => {
    if (r.url().endsWith('/api/explore') && r.method() === 'POST') {
      bodies.push(r.postDataJSON() as (typeof bodies)[number]);
    }
  });
  await page.goto('/explorer?m=rounds&g=year&v=table');
  const card = page.getByRole('region', { name: 'Rounds by year', exact: true });
  await expect(card.getByRole('table')).toBeVisible(FIRST_RESULT);
  const inlineRows = await card.getByRole('table').getByRole('row').count();
  // The page's own query keeps the time window and the 500-row limit.
  expect(bodies[0]?.limit).toBe(500);
  expect(bodies[0]?.filters.date_from).not.toBeNull();

  await card.getByRole('button', { name: 'Fullscreen' }).click();
  const dialog = page.getByRole('dialog', { name: 'Rounds by year' });
  await expect(dialog.getByText('Every Sunday on record, not just the time window.')).toBeVisible(
    FIRST_RESULT,
  );
  const full = bodies.find((b) => b.limit === 5000);
  expect(full, 'fullscreen posts a 5,000-row query').toBeDefined();
  expect(full?.filters.date_from).toBeNull();
  expect(full?.filters.date_to).toBeNull();
  // Expectations come from the API itself, asked the same way.
  const api = (await (await page.request.post('/api/explore', { data: full })).json()) as {
    rows: unknown[];
  };
  const fullRows = await dialog.getByRole('table').getByRole('row').count();
  expect(fullRows).toBe(1 + api.rows.length);
  expect(fullRows).toBeGreaterThan(inlineRows);

  await dialog.getByRole('button', { name: 'Close' }).click();
  const download = page.waitForEvent('download');
  await card.getByRole('button', { name: 'CSV' }).click();
  const file = await download;
  const text = (await readFile(await file.path(), 'utf8')).replace(/^\uFEFF/, '');
  expect(text.trimEnd().split('\r\n')).toHaveLength(1 + api.rows.length);

  // The fullscreen sheet itself, at phone width.
  await page.setViewportSize({ width: 390, height: 844 });
  await card.getByRole('button', { name: 'Fullscreen' }).click();
  await expect(page.getByRole('dialog', { name: 'Rounds by year' })).toBeVisible();
  await whenSettled(page);
  await expectNoSideScroll(page);
});

interface Meta {
  first_score_date: string;
  last_score_date: string;
}

async function meta(page: Page): Promise<Meta> {
  return (await (await page.request.get('/api/meta')).json()) as Meta;
}

test('an old From and To link becomes a Custom window and the boxes are gone', async ({ page }) => {
  const { first_score_date: first, last_score_date: last } = await meta(page);
  const bodies: { filters: Record<string, string | null> }[] = [];
  page.on('request', (r) => {
    if (r.url().endsWith('/api/explore') && r.method() === 'POST') {
      bodies.push(r.postDataJSON() as (typeof bodies)[number]);
    }
  });
  await page.goto(`/explorer?m=rounds&g=year&from=${first}&to=${last}`);
  await expect(page.getByRole('img', { name: 'Rounds by year' })).toBeVisible(FIRST_RESULT);
  await expect(page).toHaveURL(new RegExp(`w=${first}\\.\\.${last}`));
  await expect(page).not.toHaveURL(/[?&](from|to)=/);
  // One query, over the converted dates: never one over the header window first.
  expect(bodies).toHaveLength(1);
  expect(bodies[0]?.filters.date_from).toBe(first);
  expect(bodies[0]?.filters.date_to).toBe(last);
  await whenSettled(page);
  await expectNoSideScroll(page);
  // With the Filters panel open (its sliders announce their values, so after the settled check).
  await page.getByText('Filters', { exact: true }).click();
  await expect(page.getByLabel('From', { exact: true })).toHaveCount(0);
  await expect(page.getByLabel('To', { exact: true })).toHaveCount(0);
  await expectNoSideScroll(page);
});

test('a short window opens on Sunday, All time on Year, and a thin split gets a nudge', async ({
  page,
}) => {
  await page.goto('/explorer?m=rounds');
  await expect(page.getByLabel('Group by')).toHaveValue('event', FIRST_RESULT);
  await page.goto('/explorer?m=rounds&w=all');
  await expect(page.getByLabel('Group by')).toHaveValue('year');

  // Split by weather with the default 8 weeks: the nudge names the real count from the API.
  const { last_score_date: last } = await meta(page);
  const from = new Date(`${last}T12:00:00Z`);
  from.setUTCDate(from.getUTCDate() - 55);
  const events = (await (
    await page.request.get(`/api/events?from=${from.toISOString().slice(0, 10)}&to=${last}`)
  ).json()) as { has_scores: boolean }[];
  const n = events.filter((e) => e.has_scores).length;
  await page.goto('/explorer?m=rounds&g=temp_band');
  await expect(page.getByRole('img', { name: 'Rounds by temperature' })).toBeVisible(FIRST_RESULT);
  const nudge = page.getByRole('note').filter({ hasText: 'longer window' });
  if (n < 12) {
    await expect(nudge).toContainText(`${thinCount(n)} in the last 8 weeks`);
    for (const button of await nudge.getByRole('button').all()) {
      expect((await button.boundingBox())?.height).toBeGreaterThanOrEqual(44);
    }
    await expectNoSideScroll(page);
    await nudge.getByRole('button', { name: 'Show all time' }).click();
    await expect(page).toHaveURL(/w=all/);
    await expect(nudge).toHaveCount(0);
  } else {
    await expect(nudge).toHaveCount(0);
  }
});
