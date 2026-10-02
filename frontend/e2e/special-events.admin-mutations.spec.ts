import type { Page } from '@playwright/test';
import { ADMIN_STATE } from './authState';
import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

// Project `admin-mutations` (matched by the unanchored /admin-mutations\.spec\.ts/): one worker, after
// every read-only spec. The special Sunday is rolled back in `finally`, so the shared seed and the
// read-only specs' counts never see it. A run that dies between commit and roll back needs `down -v`.
test.use({ storageState: ADMIN_STATE });

const FILE = 'e2e/fixtures/special_2026-09-20.xlsx';
const DATE = '2026-09-20';
const LABEL = '3-Bird Shoot';
const VIEWPORTS = [
  { width: 390, height: 844 },
  { width: 1440, height: 900 },
] as const;
const BEST_SCORES = '/api/leaderboards?period=all_time&metric=best_score';
const SLOW = { timeout: 15_000 };

type Shooter = { shooter_id: number; display_name: string };
type Odometer = { events: number; current_streak: number; rounds: number; clays_thrown: number };
type Board = { rows: { shooter_id: number; value: number; rank: number }[] };

async function apiJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), path).toBe(true);
  return (await response.json()) as T;
}

async function hadleyId(page: Page): Promise<number> {
  const found = await apiJson<Shooter[]>(page, '/api/shooters?q=Hadley');
  const hadley = found.find((s) => s.display_name === 'Hadley, Ike');
  expect(hadley, 'Hadley, Ike in the seed').toBeDefined();
  return (hadley as Shooter).shooter_id;
}

async function odometer(page: Page, id: number): Promise<Odometer> {
  return (await apiJson<{ odometer: Odometer }>(page, `/api/shooters/${id}`)).odometer;
}

async function rollBack(page: Page): Promise<void> {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/admin');
  const row = page
    .getByRole('table', { name: 'Import history' })
    .getByRole('row', { name: /special_2026-09-20\.xlsx/ })
    .first();
  await expect(row).toContainText('Committed');
  await row.getByRole('button', { name: 'Roll back' }).click();
  await row.getByRole('button', { name: 'Confirm roll back' }).click();
  await expect(page.getByText(/^Rolling back #\d+: Done$/)).toBeVisible({ timeout: 120_000 });
  await expect(row).toContainText('Rolled back');
}

test('a special shoot: preview, commit, every page at both sizes, unchanged scores, then roll back', async ({
  page,
}) => {
  test.setTimeout(420_000);
  const id = await hadleyId(page);
  const before = await odometer(page, id);
  const boardBefore = await apiJson<Board>(page, BEST_SCORES);
  expect((await page.request.get(`/api/events/${DATE}`)).status()).toBe(404);

  let committed = false;
  try {
    await page.goto('/admin');
    await page.getByLabel('Workbook (.xlsx)').setInputFiles(FILE);
    await page.getByRole('button', { name: 'Upload and preview' }).click();
    const changes = page.getByRole('region', { name: 'Changes' });
    await expect(changes).toContainText(LABEL);
    await expect(changes).toContainText('60 (10 stations)');
    await expect(changes).toContainText('Shooters5');
    // "New names" is not asserted: the new shooter stays after a roll back, so a repeat run has none.
    await expect(page.getByText('Special shoot workbook').first()).toBeVisible();
    await page.getByRole('button', { name: 'Commit import' }).click();
    committed = true;
    await expect(page.getByText('Rebuilding live data: Done')).toBeVisible({ timeout: 120_000 });

    for (const viewport of VIEWPORTS) {
      await page.setViewportSize(viewport);

      await page.goto('/events?year=2026');
      await expect(
        page.getByRole('list', { name: 'Sundays in 2026' }).getByRole('listitem'),
      ).toHaveCount(37);
      await expect(page.getByText(`${LABEL} · Special · 60 · 5 shooters`)).toBeVisible();
      await expect(
        page
          .getByRole('region', { name: 'Calendar 2026' })
          .getByRole('link', { name: `Sep 20, 2026 — ${LABEL}, special shoot, 5 shooters` }),
      ).toBeVisible();
      await whenSettled(page);
      await expectNoSideScroll(page);

      await page.goto(`/events/${DATE}`);
      await expect(page.getByText(`${LABEL} · Special · 60 targets`)).toBeVisible();
      await expect(
        page.getByRole('note').filter({ hasText: 'counts as a Sunday shot' }),
      ).toBeVisible();
      const results = page.getByRole('table', { name: 'Results' });
      await expect(results.getByRole('columnheader', { name: 'Score (of 60)' })).toBeVisible();
      await expect(results.getByRole('row')).toHaveCount(6);
      await expect(results.getByRole('row').nth(1)).toContainText('Hadley, Ike');
      await expect(results.getByRole('row').nth(1)).toContainText('55');
      await expect(page.getByRole('region', { name: 'vs previous Sunday' })).toHaveCount(0);
      await expect(
        page.getByRole('img', { name: 'Station hits heatmap for Sep 20, 2026' }),
      ).toBeVisible(SLOW);
      await expect(
        page.getByRole('list', { name: 'Trophies earned today' }).getByText(LABEL).first(),
      ).toBeVisible(SLOW);
      await whenSettled(page);
      await expectNoSideScroll(page);

      await page.goto(`/shooters/${id}`);
      const card = page.getByRole('region', { name: 'Special shoots' });
      await expect(card).toContainText(`${LABEL} · Special · 60`, SLOW);
      await expect(card).toContainText('55 of 60');
      await whenSettled(page);
      await expectNoSideScroll(page);
    }

    // Appearance numbers move; score numbers do not (Review Focus 1 and 3).
    const after = await odometer(page, id);
    expect(after.events).toBe(before.events + 1);
    expect(after.current_streak).toBe(before.current_streak + 1);
    expect(after.rounds).toBe(before.rounds);
    expect(after.clays_thrown).toBe(before.clays_thrown);
    expect((await apiJson<Board>(page, BEST_SCORES)).rows).toEqual(boardBefore.rows);
  } finally {
    if (committed) await rollBack(page);
  }

  expect((await page.request.get(`/api/events/${DATE}`)).status()).toBe(404);
  expect(await odometer(page, id)).toEqual(before);
});
