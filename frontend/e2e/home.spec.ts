import { readFile } from 'node:fs/promises';

import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

/** C10: every visible link and button on the page is at least 44×44 px. */
async function expectTapTargets(page: Page): Promise<void> {
  const targets = page.getByRole('main').locator('a, button');
  const small: string[] = [];
  for (const target of await targets.all()) {
    if (!(await target.isVisible())) continue;
    const box = await target.boundingBox();
    if (box === null || box.height < 44 || box.width < 44) {
      const name =
        (await target.textContent())?.trim() || (await target.getAttribute('aria-label'));
      small.push(`${name}: ${box === null ? 'no box' : `${box.width}×${box.height}`}`);
    }
  }
  expect(small).toEqual([]);
}

test('home shows the latest event, the club pulse and the me prompt', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Sep 27, 2026' }).first()).toBeVisible();
  await expect(page.getByText('Winners: Finnegan, Stanton & Stockton, Ethan — 49')).toBeVisible();
  await expect(page.getByText('Turnout per Sunday', { exact: true })).toBeVisible();
  await expect(page.getByText(/tap “That’s me”/)).toBeVisible();
});

test('the latest event link opens the full results', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Full results' }).click();
  await expect(page).toHaveURL(/\/events\/2026-09-27$/);
});

test('every home tap target is at least 44px with the me prompt', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible();
  await expect(page.getByText(/tap “That’s me”/)).toBeVisible();
  await expectTapTargets(page);
});

test('every home tap target is at least 44px with a me id', async ({ page }) => {
  const response = await page.request.get('/api/shooters?q=Hadley');
  expect(response.status()).toBe(200);
  const shooters = (await response.json()) as { shooter_id: number; display_name: string }[];
  const hadley = shooters.find((s) => s.display_name === 'Hadley, Ike');
  expect(hadley).toBeDefined();
  await page.addInitScript((id) => localStorage.setItem('sc.me', String(id)), hadley?.shooter_id);
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible();
  await expect(page.getByText('Last out')).toBeVisible();
  await expectTapTargets(page);
});

test('the turnout chart and the club numbers explain themselves and name the time window', async ({
  page,
}) => {
  await page.goto('/');
  const chart = page.getByRole('region', { name: 'Turnout per Sunday' });
  await expect(chart.getByRole('button', { name: 'CSV' })).toBeVisible();
  const about = chart.getByRole('button', { name: 'About this chart' });
  await about.click();
  await expect(chart.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  await expect(chart.getByRole('heading', { name: "How it's worked out" })).toBeVisible();
  await expect(chart.getByText('Last 8 weeks').first()).toBeVisible();
  const pulse = page.getByRole('region', { name: 'Club pulse' });
  await pulse.getByRole('button', { name: 'About Highest score' }).click();
  await expect(pulse.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  await whenSettled(page);
  await expectNoSideScroll(page);
});

test('the window follows the time window control: stats come from the chosen period', async ({
  page,
}) => {
  const metaResponse = await page.request.get('/api/meta');
  const anchor = ((await metaResponse.json()) as { last_score_date: string }).last_score_date;
  const listed = await page.request.get(`/api/events?year=${anchor.slice(0, 4)}`);
  const events = (await listed.json()) as { has_scores: boolean; top_score: number | null }[];
  const best = Math.max(...events.filter((e) => e.has_scores).map((e) => e.top_score ?? 0));
  await page.goto('/?w=ytd');
  const pulse = page.getByRole('region', { name: 'Club pulse' });
  await expect(pulse.getByText('This year to date').first()).toBeVisible();
  // The tile is the innermost block holding both this stat's About button and its value.
  await expect(
    pulse
      .locator('div')
      .filter({ has: page.getByRole('button', { name: 'About Highest score' }) })
      .filter({ hasText: String(best) })
      .last(),
  ).toBeVisible();
});

test('the phone top bar keeps its brand, filter and time window on one row', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'the top bar only exists below 1024 px');
  for (const width of [360, 390, 414]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto('/');
    const header = page.locator('header').first();
    await expect(header).toBeVisible();
    const select = header.getByRole('combobox', { name: 'Time window' });
    await expect(select).toBeVisible();
    // Short labels on screen, the full wording for assistive tech.
    expect(
      await select.evaluate((el: HTMLSelectElement) => el.selectedOptions[0]?.textContent),
    ).toBe('8W');
    await expect(select).toHaveAccessibleDescription('Last 8 weeks');
    const tops = await header
      .locator(':scope > *')
      .evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().top)));
    expect(tops.length).toBeGreaterThanOrEqual(3);
    expect(new Set(tops).size, `children start on different rows at ${width} px`).toBe(1);
    const box = await header.boundingBox();
    expect(box?.height ?? 0, `header height at ${width} px`).toBeLessThanOrEqual(64);
    await expectNoSideScroll(page);
  }
});

test('the turnout chart lists and exports every Sunday on record, not just the time window', async ({
  page,
}) => {
  // Every scored Sunday, year by year, read from the API at run time.
  const meta = (await (await page.request.get('/api/meta')).json()) as {
    first_event_date: string;
    last_score_date: string;
  };
  const first = Number(meta.first_event_date.slice(0, 4));
  const last = Number(meta.last_score_date.slice(0, 4));
  let scored = 0;
  for (let year = first; year <= last; year += 1) {
    const events = (await (await page.request.get(`/api/events?year=${year}`)).json()) as {
      has_scores: boolean;
    }[];
    scored += events.filter((e) => e.has_scores).length;
  }
  expect(scored).toBeGreaterThan(0);

  await page.goto('/');
  const chart = page.getByRole('region', { name: 'Turnout per Sunday' });
  const download = page.waitForEvent('download');
  await chart.getByRole('button', { name: 'CSV' }).click({ timeout: 15_000 });
  const file = await download;
  const text = (await readFile(await file.path(), 'utf8')).replace(/^\uFEFF/, '');
  expect(text.trimEnd().split('\r\n')).toHaveLength(scored + 1);

  await chart.getByRole('button', { name: 'Table' }).click();
  await expect(chart.getByRole('row').nth(1)).toBeVisible();
  const inlineRows = await chart.getByRole('row').count();
  expect(inlineRows - 1).toBeLessThan(scored);
  await page.setViewportSize({ width: 1440, height: 900 });
  await chart.getByRole('button', { name: 'Fullscreen' }).click();
  const dialog = page.getByRole('dialog', { name: 'Turnout per Sunday' });
  await expect(dialog.getByRole('row')).toHaveCount(scored + 1);
  await page.keyboard.press('Escape');

  await page.setViewportSize({ width: 390, height: 844 });
  await chart.getByRole('button', { name: 'Fullscreen' }).click();
  await expect(dialog.getByRole('row')).toHaveCount(scored + 1);
  await expectNoSideScroll(page);
});
