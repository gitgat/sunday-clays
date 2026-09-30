import type { Page } from '@playwright/test';
import { ADMIN_STATE } from './authState';
import { expect, test } from './fixtures';

test.use({ storageState: ADMIN_STATE });

/** The duplicates queue compares every key pair on a cold data version, so its first load can be slow. */
const QUEUE = { timeout: 15_000 };

type Side = { display_name: string; n_rounds: number };
type Pair = { a: Side; b: Side };

/** The data under test comes from the API at run time, never from hard-coded member names. */
async function apiJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok()).toBe(true);
  return (await response.json()) as T;
}

test('identity page lists possible duplicates, the rule list and the typed rule forms', async ({
  page,
}) => {
  const pairs = await apiJson<Pair[]>(page, '/api/admin/possible-duplicates');
  const rules = await apiJson<unknown[]>(page, '/api/admin/rules');
  expect(pairs.length).toBeGreaterThan(0);
  const first = pairs[0] as Pair;

  await page.goto('/admin/identity');
  await expect(page.getByRole('heading', { level: 1, name: 'Identity & rules' })).toBeVisible();
  const list = page.getByRole('list', { name: 'Possible duplicates' });
  await expect(list.getByRole('listitem')).toHaveCount(pairs.length, QUEUE);
  await expect(
    list
      .getByRole('listitem')
      .filter({ hasText: first.a.display_name })
      .filter({ hasText: first.b.display_name })
      .first(),
  ).toBeVisible();
  if (rules.length === 0) await expect(page.getByText('No rules yet.')).toBeVisible();
  else await expect(page.getByRole('table', { name: 'Rules' })).toBeVisible();
  await expect(page.getByLabel('Rule type').locator('option')).toHaveCount(8);
});

test('a merge preview shows the shared-date check and can be cancelled', async ({ page }) => {
  const pairs = await apiJson<Pair[]>(page, '/api/admin/possible-duplicates');
  // The last pair sits far down the queue: the confirmation must still appear on screen.
  const { a, b } = pairs[pairs.length - 1] as Pair;
  await page.goto('/admin/identity');
  await page
    .getByRole('button', { name: `Merge ${a.display_name} into ${b.display_name}`, exact: true })
    .first()
    .click(QUEUE);
  // The dry run creates nothing (C8), so this spec stays read-only.
  const confirm = page.getByRole('region', { name: 'Confirm merge' });
  await expect(confirm).toContainText(/No shared dates\.|of the same dates/);
  await expect(confirm).toBeInViewport();
  await confirm.getByRole('button', { name: 'Cancel' }).click();
  await expect(confirm).toHaveCount(0);
});

test('the page fits the viewport and its actions are at least 44 px tall', async ({ page }) => {
  await page.goto('/admin/identity');
  const list = page.getByRole('list', { name: 'Possible duplicates' });
  await expect(list.getByRole('listitem').first()).toBeVisible(QUEUE);
  await expect(page.getByLabel('Rule type')).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  const merge = list.getByRole('button', { name: /^Merge / }).first();
  await expect(merge).toBeInViewport({ ratio: 1 });
  expect((await merge.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  // The rules table (stacked cards on mobile) must not scroll sideways either.
  const rules = page.getByRole('table', { name: 'Rules' });
  if ((await rules.count()) > 0) {
    const inner = await rules.evaluate((t) => t.scrollWidth - t.clientWidth);
    expect(inner).toBeLessThanOrEqual(0);
  }
});

test('the station reset form takes a station label such as 7A, upper-cased, without submitting', async ({
  page,
}) => {
  await page.goto('/admin/identity');
  await page.getByLabel('Rule type').selectOption('station_reset');
  const station = page.getByLabel('Station (like 7 or 7A)');
  await station.fill('7a');
  await expect(station).toHaveValue('7A');
  // A label is text, not a number spinner, and the form stays a phone-sized column.
  await expect(station).toHaveAttribute('type', 'text');
  expect((await station.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  // Read-only: the rule is incomplete (no date or note), so nothing can be created.
  await expect(page.getByRole('button', { name: 'Create rule' })).toBeDisabled();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
