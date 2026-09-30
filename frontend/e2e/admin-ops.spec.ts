import { ADMIN_STATE } from './authState';
import { expect, test } from './fixtures';

test.use({ storageState: ADMIN_STATE });

type Issue = { code: string; severity: string };

test('ops page groups the data issues and shows the audit log and recompute controls', async ({
  page,
}) => {
  // Read what the server holds at run time: no hard-coded counts, names or dates.
  const issues = (await (await page.request.get('/api/admin/data-issues')).json()) as Issue[];
  const audit = (await (await page.request.get('/api/admin/audit')).json()) as unknown[];
  const groups = new Map<string, { severity: string; n: number }>();
  for (const issue of issues) {
    const group = groups.get(issue.code);
    groups.set(issue.code, { severity: issue.severity, n: (group?.n ?? 0) + 1 });
  }
  expect(audit.length, 'seeding the two imports writes audit rows').toBeGreaterThan(0);

  await page.goto('/admin/ops');
  await expect(page.getByRole('heading', { level: 1, name: 'Data & ops' })).toBeVisible();
  for (const [code, { severity, n }] of groups) {
    await expect(page.getByText(`${code} (${n}) · ${severity}`, { exact: true })).toBeVisible();
  }
  // Seeded fixture facts (C4/C5): rebuild must have written these two issues.
  await expect(page.getByText(/^incomplete_results \(1\)/)).toBeVisible();
  await expect(page.getByText(/^station_score_mismatch \(1\)/)).toBeVisible();
  expect(groups.size).toBeGreaterThan(0);

  const log = page.getByRole('table', { name: 'Audit log' });
  await expect(log.getByRole('row')).toHaveCount(audit.length + 1);
  await expect(page.getByRole('button', { name: 'Recompute analytics' })).toBeEnabled();
  await expect(page.getByRole('switch', { name: 'Recalibrate skill model' })).toBeVisible();
});

test('nothing overflows horizontally and the controls are 44 px tall', async ({ page }) => {
  await page.goto('/admin/ops');
  const log = page.getByRole('table', { name: 'Audit log' });
  await expect(log).toBeVisible();
  await expect(page.getByText(/^incomplete_results \(1\)/)).toBeVisible();
  await expect(page.getByText(/^station_score_mismatch \(1\)/)).toBeVisible();
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    const table = document.querySelector('table[aria-label="Audit log"]');
    const parent = table?.parentElement;
    return {
      page: doc.scrollWidth - doc.clientWidth,
      table: parent ? parent.scrollWidth - parent.clientWidth : 0,
    };
  });
  expect(overflow.page).toBeLessThanOrEqual(0);
  expect(overflow.table).toBeLessThanOrEqual(0);

  const recompute = page.getByRole('button', { name: 'Recompute analytics' });
  await recompute.scrollIntoViewIfNeeded();
  expect((await recompute.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  const toggle = page.getByRole('switch', { name: 'Recalibrate skill model' });
  expect((await toggle.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  const link = page.getByRole('link', { name: /^Shooter #/ }).first();
  await link.scrollIntoViewIfNeeded();
  expect((await link.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
});
