import { expect, test } from './fixtures';

test('directory search finds a deceased shooter whose profile shows the memorial marker and odometer', async ({
  page,
}) => {
  await page.goto('/shooters');
  await page.getByRole('searchbox', { name: 'Search shooters' }).fill('Gilchrist');
  await page.getByRole('link', { name: /Gilchrist, Melvin/ }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Gilchrist, Melvin' })).toBeVisible();
  await expect(page.getByText('In memoriam', { exact: true })).toBeVisible();
  const odometer = page.getByRole('list', { name: 'Lifetime odometer' });
  await expect(odometer.getByRole('listitem').filter({ hasText: 'Clays thrown' })).toContainText(
    '550',
  );
  await expect(odometer.getByRole('listitem').filter({ hasText: 'Clays broken' })).toContainText(
    '409',
  );
  await expect(page.getByText('Stats', { exact: true })).toBeVisible();
});

test("That's me marks the profile as yours", async ({ page }) => {
  await page.goto('/shooters?q=Hadley');
  await page.getByRole('link', { name: /Hadley, Ike/ }).click();
  await page.getByRole('button', { name: "That's me" }).click();
  await expect(page.getByRole('button', { name: 'This is you' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
});
