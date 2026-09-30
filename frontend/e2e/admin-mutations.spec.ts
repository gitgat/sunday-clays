import { ADMIN_STATE } from './authState';
import { expect, test } from './fixtures';

// Project `admin-mutations` (Step 2): desktop only, one worker, after every read-only spec.
// Re-runs on the same stack: a rolled-back variant is not a duplicate. Only a run that died between commit and
// roll back leaves the variant committed and needs a fresh stack (`down -v`).
test.use({ storageState: ADMIN_STATE });

test('re-uploading a seeded workbook shows the already-imported notice', async ({ page }) => {
  await page.goto('/admin');
  await page
    .getByLabel('Workbook (.xlsx)')
    .setInputFiles('../backend/tests/fixtures/stations_2026-09-27.xlsx');
  await page.getByRole('button', { name: 'Upload and preview' }).click();
  await expect(
    page.getByText(/^Already imported as import #\d+\. Nothing to commit\.$/),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Commit import' })).toHaveCount(0);
});

test('upload, commit and roll back a stations variant', async ({ page }) => {
  test.setTimeout(300_000);
  await page.goto('/admin');
  await page.getByLabel('Workbook (.xlsx)').setInputFiles('e2e/fixtures/stations_variant.xlsx');
  await page.getByRole('button', { name: 'Upload and preview' }).click();
  await expect(page.getByRole('region', { name: 'Station vs score' })).toContainText(
    'Marsden, Wylie',
  );
  await expect(page.getByText('Weeks replaced')).toBeVisible();
  await page.getByRole('button', { name: 'Commit import' }).click();
  await expect(page.getByText('Rebuilding live data: Done')).toBeVisible({ timeout: 120_000 });

  await page.goto('/admin');
  // History is newest first; a rolled-back variant is not a duplicate, so a repeat run adds a row.
  const row = page
    .getByRole('table', { name: 'Import history' })
    .getByRole('row', { name: /stations_variant\.xlsx/ })
    .first();
  await expect(row).toContainText('Committed');
  await row.getByRole('button', { name: 'Roll back' }).click();
  await row.getByRole('button', { name: 'Confirm roll back' }).click();
  await expect(page.getByText(/^Rolling back #\d+: Done$/)).toBeVisible({ timeout: 120_000 });
  await expect(row).toContainText('Rolled back');
});
