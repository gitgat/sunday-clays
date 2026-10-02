import { request as pwRequest, type APIRequestContext, type Page } from '@playwright/test';
import { ADMIN_STATE } from './authState';
import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

// Project `admin-mutations` (matched by the unanchored /admin-mutations\.spec\.ts/): one worker, after
// every read-only spec. The special Sunday is rolled back in `finally`, so the shared seed and the
// read-only specs' counts never see it. The roll back is in `test.afterEach` on a fresh request context,
// so it also runs after a timeout or a closed page. Only a run that dies outright between commit and
// roll back needs `down -v`.
// On a reused stack the new shooter (Kim, Pat) stays in the directory after the roll back, so a repeat
// run has no new names. That is why the preview is checked for `Shooters5`, not for "New names".
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

type ImportRow = { id: number; filename: string; status: string };

let committedImportId: number | null = null;
let hadleyBefore: { id: number; odometer: Odometer } | null = null;

async function rollBackAndWait(api: APIRequestContext, importId: number): Promise<void> {
  const rolled = await api.post(`/api/admin/imports/${importId}/rollback`);
  if (!rolled.ok()) throw new Error(`roll back of import #${importId}: HTTP ${rolled.status()}`);
  const { job_id: jobId } = (await rolled.json()) as { job_id: number };
  await expect
    .poll(
      async () =>
        ((await (await api.get(`/api/admin/jobs/${jobId}`)).json()) as { status: string }).status,
      { timeout: 120_000 },
    )
    .toBe('done');
}

test.afterEach(async ({ baseURL }, testInfo) => {
  if (committedImportId === null) return;
  const importId = committedImportId;
  committedImportId = null;
  const api = await pwRequest.newContext({ baseURL, storageState: ADMIN_STATE });
  try {
    try {
      await rollBackAndWait(api, importId);
    } catch (error) {
      // Never mask the test's own failure: record the cleanup problem and move on.
      testInfo.annotations.push({ type: 'cleanup-error', description: String(error) });
      console.error(`special-events cleanup failed (import #${importId}):`, error);
      return;
    }
    if (testInfo.status === 'passed' && hadleyBefore) {
      expect((await api.get(`/api/events/${DATE}`)).status()).toBe(404);
      const after = (await (await api.get(`/api/shooters/${hadleyBefore.id}`)).json()) as {
        odometer: Odometer;
      };
      expect(after.odometer).toEqual(hadleyBefore.odometer);
      const rows = (await (await api.get('/api/admin/imports')).json()) as ImportRow[];
      expect(rows.find((r) => r.id === importId)?.status).toBe('rolled_back');
    }
  } finally {
    await api.dispose();
  }
});

test('a special shoot: preview, commit, every page at both sizes, unchanged scores, then roll back', async ({
  page,
}) => {
  test.setTimeout(420_000);
  const id = await hadleyId(page);
  const before = await odometer(page, id);
  hadleyBefore = { id, odometer: before };
  const boardBefore = await apiJson<Board>(page, BEST_SCORES);
  expect((await page.request.get(`/api/events/${DATE}`)).status()).toBe(404);

  {
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
    await expect(page.getByText('Rebuilding live data: Done')).toBeVisible({ timeout: 120_000 });
    const rows = await apiJson<ImportRow[]>(page, '/api/admin/imports');
    const mine = rows.find(
      (r) => r.filename === 'special_2026-09-20.xlsx' && r.status === 'committed',
    );
    expect(mine, 'the committed special import in the history').toBeDefined();
    committedImportId = (mine as ImportRow).id;

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
      const header = page
        .locator('header')
        .filter({ has: page.getByRole('heading', { level: 1 }) });
      await expect(header.getByText(`${LABEL} · Special · 60 targets`)).toBeVisible();
      // The shareable card carries the same line and the scores out of the total, never "Sporting".
      const share = page.getByRole('region', { name: 'Shareable results card' });
      await expect(share).toContainText(`${LABEL} · Special · 60 targets · 5 shooters`);
      await expect(share).toContainText('55 of 60');
      await expect(share).not.toContainText('Sporting');
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
  }
});
