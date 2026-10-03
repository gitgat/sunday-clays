import { ADMIN_STATE } from './authState';
import { expect, test } from './fixtures';
import { expectNoSideScroll, expectTapTargets, whenSettled } from './layout';

// Read-only: lists the switches; flipping them is the admin-mutations project's job (Task 10).
test.use({ storageState: ADMIN_STATE });

const LABELS = [
  'Link previews',
  'Welcome tour and glossary',
  'Weekly recap',
  'Add to Home Screen',
  'Club milestones',
  'Summary card',
];

test('the Features page lists the six launch switches', async ({ page }) => {
  await page.goto('/admin/features');
  await expect(page.getByRole('heading', { level: 1, name: 'Features' })).toBeVisible();
  await whenSettled(page);
  for (const label of LABELS) {
    await expect(page.getByRole('switch', { name: label })).toBeVisible();
  }
  await expect(page.getByRole('switch')).toHaveCount(LABELS.length);
  await expect(
    page.getByText(/^(Changed [A-Z][a-z]{2} \d{1,2}, \d{4}|Never changed)$/),
  ).toHaveCount(LABELS.length);
  await expectNoSideScroll(page);
  await expectTapTargets(page);
});

test('the nav lists Features for an admin', async ({ page, isMobile }) => {
  await page.goto('/');
  if (isMobile) await page.getByRole('button', { name: 'More' }).click();
  await expect(page.getByRole('link', { name: 'Features' })).toBeVisible();
});
