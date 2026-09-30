import { ADMIN_STATE } from './authState';
import { expect, test } from './fixtures';

test.use({ storageState: ADMIN_STATE });

test('import history lists the seeded workbooks', async ({ page }) => {
  await page.goto('/admin');
  await expect(page.getByRole('heading', { level: 1, name: 'Imports' })).toBeVisible();
  const history = page.getByRole('table', { name: 'Import history' });
  await expect(history.getByRole('row', { name: /scores_2026-09-27\.xlsx/ })).toContainText(
    'Committed',
  );
  await expect(history.getByRole('row', { name: /stations_2026-09-27\.xlsx/ })).toContainText(
    'Committed',
  );
  await expect(page.getByLabel('Workbook (.xlsx)')).toBeVisible();
});

test('the history fits the viewport: readable filenames, reachable 44 px actions', async ({
  page,
}) => {
  await page.goto('/admin');
  const history = page.getByRole('table', { name: 'Import history' });
  const row = history.getByRole('row', { name: /stations_2026-09-27\.xlsx/ });
  await expect(row).toContainText('Committed');
  // No horizontal scroll on the page or inside the table.
  const overflow = await page.evaluate(() => ({
    page: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    table: (() => {
      const t = document.querySelector('table[aria-label="Import history"]');
      const parent = t?.parentElement;
      return parent ? parent.scrollWidth - parent.clientWidth : 0;
    })(),
  }));
  expect(overflow.page).toBeLessThanOrEqual(0);
  expect(overflow.table).toBeLessThanOrEqual(0);
  // The filename reads as a line, not a column of 3-character fragments.
  const link = await row.getByRole('link').boundingBox();
  expect(link?.width ?? 0).toBeGreaterThan(150);
  expect(link?.height ?? 0).toBeLessThan(80);
  // The action is on screen (not clipped), at least 44 px tall, and its confirmation stays in view too.
  const rollBack = row.getByRole('button', { name: 'Roll back' });
  await expect(rollBack).toBeInViewport({ ratio: 1 });
  expect((await rollBack.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  await rollBack.click();
  const confirm = row.getByRole('button', { name: 'Confirm roll back' });
  await expect(confirm).toBeInViewport({ ratio: 1 });
  await expect(row.getByRole('button', { name: 'Cancel' })).toBeInViewport({ ratio: 1 });
  await row.getByRole('button', { name: 'Cancel' }).click();
});

test('a committed import shows its preview layout without commit controls', async ({ page }) => {
  await page.goto('/admin');
  await page
    .getByRole('table', { name: 'Import history' })
    .getByRole('link', { name: 'scores_2026-09-27.xlsx' })
    .click();
  await expect(page.getByRole('heading', { level: 1, name: /^Import #\d+$/ })).toBeVisible();
  await expect(page.getByText('Changes', { exact: true })).toBeVisible();
  await expect(page.getByText('non_sunday_date (2) · warning')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Commit import' })).toHaveCount(0);
});
