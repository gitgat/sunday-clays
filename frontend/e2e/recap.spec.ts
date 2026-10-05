import { readFileSync } from 'node:fs';
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
  await expect(text).toHaveValue(/Turnout: /);
  // The club newsletter covers the podium; the recap has no podium section and no link.
  await expect(text).not.toHaveValue(/See every score|Podium/);
  await page.getByRole('button', { name: 'Copy text' }).click();
  await expect(page.getByText('Copied.')).toBeVisible();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied.startsWith('Sunday Clays · Sunday, September 27, 2026')).toBe(true);
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download image' }).click();
  const saved = await download;
  expect(saved.suggestedFilename()).toBe('sunday-clays-recap-2026-09-27.png');
  // The PNG is drawn from the fixed 600 px card at 2x, on a phone as on a desktop.
  const path = await saved.path();
  const header = readFileSync(path).subarray(16, 20);
  expect(header.readUInt32BE(0)).toBe(1200);
  await expectNoSideScroll(page);
});
