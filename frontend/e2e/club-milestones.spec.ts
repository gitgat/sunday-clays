import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

test('the Home card links to the Club milestones', async ({ page }) => {
  await page.goto('/');
  const card = page.getByRole('region', { name: /^Club milestone/ });
  await expect(card).toBeVisible();
  await card.getByRole('link', { name: 'All club milestones' }).click();
  await expect(page).toHaveURL(/\/club#milestones$/);
  await expect(page.getByRole('heading', { level: 2, name: /^Milestones/ })).toBeVisible();
});

test('the totals chart has Table, CSV, fullscreen and an explainer', async ({ page }) => {
  await page.goto('/club?w=all');
  await whenSettled(page);
  const chart = page.getByRole('region', { name: 'Club totals over time' });
  await expect(chart).toBeVisible();
  await chart.getByRole('button', { name: 'About this chart' }).click();
  await expect(chart.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  const download = page.waitForEvent('download');
  await chart.getByRole('button', { name: 'CSV' }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^club-totals.*\.csv$/);
  const csv = await (await file.createReadStream()).toArray();
  expect(Buffer.concat(csv).toString('utf8')).toContain(
    'Sunday,Clays thrown,Sundays held,Shooters,Rounds',
  );
  await chart.getByRole('button', { name: 'Fullscreen' }).click();
  await expect(page.getByRole('dialog', { name: 'Club totals over time' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expectNoSideScroll(page);
});

test('the window trims the inline table, not the data', async ({ page }) => {
  const rowsAt = async (w: string) => {
    await page.goto(`/club?w=${w}&ctot=table`);
    await whenSettled(page);
    const region = page.getByRole('region', { name: 'Club totals over time' });
    await expect(region.getByRole('table')).toBeVisible();
    const rows = region.getByRole('row');
    // Retry until the lazy chart has swapped in and the count stops changing.
    let last = -1;
    await expect
      .poll(async () => {
        const n = await rows.count();
        const stable = n > 1 && n === last;
        last = n;
        return stable;
      })
      .toBe(true);
    return last;
  };
  const trimmed = await rowsAt('8w');
  expect(trimmed).toBeLessThan(await rowsAt('all'));
});
