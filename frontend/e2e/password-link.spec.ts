import { e2ePassword } from './authState';
import { expect, test } from './fixtures';

// Every test here starts signed out, independent of the setup project's storage state.
test.use({ storageState: { cookies: [], origins: [] } });

test('a password link logs in a viewer, lands on the page and leaves p out of the address bar', async ({
  page,
}) => {
  await page.goto(`/?rt=sporting&p=${encodeURIComponent(e2ePassword('viewer'))}`);
  await expect(page.getByText('Filtered: Sporting')).toBeVisible();
  await expect(page).toHaveURL(/\/\?rt=sporting$/);
  expect(page.url()).not.toContain('p=');
});

test('a wrong password in a link ends on the login page with a note and a clean next', async ({
  page,
}) => {
  await page.goto('/?rt=sporting&p=definitely-not-the-password');
  await expect(page).toHaveURL(/\/login\?next=%2F%3Frt%3Dsporting$/);
  await expect(
    page.getByText("That link's password didn't work. Enter the password to continue."),
  ).toBeVisible();
  expect(page.url()).not.toContain('definitely-not-the-password');
});

test('an admin password in a link is treated as wrong', async ({ page }) => {
  await page.goto(`/?p=${encodeURIComponent(e2ePassword('admin'))}`);
  await expect(page).toHaveURL(/\/login\?next=%2F$/);
  await expect(page.getByText(/link's password didn't work/)).toBeVisible();
});

test('a doubled-slash path with p still cleans the address bar and logs in', async ({ page }) => {
  await page.goto(`//?p=${encodeURIComponent(e2ePassword('viewer'))}`);
  await expect(page).not.toHaveURL(/p=/);
  expect(new URL(page.url()).pathname).toBe('/');
  await expect(page.locator('#root')).not.toBeEmpty();
});
