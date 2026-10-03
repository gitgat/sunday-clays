import { ADMIN_STATE } from './authState';
import { expect, test } from './fixtures';
import { expectNoSideScroll } from './layout';

test.use({ storageState: ADMIN_STATE });

test('the recap defaults to the latest Sunday and copies and downloads', async ({
  page,
  context,
}) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/admin/recap');
  await expect(page.getByRole('heading', { level: 1, name: /^Weekly recap/ })).toBeVisible();
  const text = page.getByRole('textbox', { name: 'Recap (plain text)' });
  await expect(text).toHaveValue(/^Sunday Clays · Sunday, September 27, 2026/);
  await expect(text).toHaveValue(/Podium/);
  await page.getByRole('button', { name: 'Copy text' }).click();
  await expect(page.getByText('Copied.')).toBeVisible();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied.startsWith('Sunday Clays · Sunday, September 27, 2026')).toBe(true);
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download image' }).click();
  expect((await download).suggestedFilename()).toBe('sunday-clays-recap-2026-09-27.png');
  await expectNoSideScroll(page);
});
