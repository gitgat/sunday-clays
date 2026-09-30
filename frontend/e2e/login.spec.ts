import type { Page } from '@playwright/test';
import { e2ePassword } from './authState';
import { expect, test } from './fixtures';

// Every test here starts signed out, independent of the setup project's storage state.
test.use({ storageState: { cookies: [], origins: [] } });

async function logIn(page: Page, password: string): Promise<void> {
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Log in' }).click();
}

/** Desktop shows the account panel in the side nav; mobile keeps it in the "More" sheet. */
async function openAccount(page: Page): Promise<void> {
  const more = page.getByRole('button', { name: 'More' });
  if (await more.isVisible()) await more.click();
}

test('a signed-out visit is sent to the login page with next', async ({ page }) => {
  await page.goto('/?rt=sporting');
  await expect(page).toHaveURL(/\/login\?next=%2F%3Frt%3Dsporting$/);
  await expect(page.getByRole('heading', { name: 'Sunday Clays' })).toBeVisible();
});

for (const role of ['viewer', 'admin'] as const) {
  test(`${role} logs in, lands on next, and logs out`, async ({ page }) => {
    await page.goto('/?rt=sporting');
    await logIn(page, e2ePassword(role));
    await expect(page).toHaveURL(/\/\?rt=sporting$/);
    await expect(page.getByText('Filtered: Sporting')).toBeVisible();
    await openAccount(page);
    await expect(page.getByText(`Signed in as ${role}`)).toBeVisible();
    await page.getByRole('button', { name: 'Log out' }).click();
    await expect(page).toHaveURL(/\/login/);
    await page.goto('/');
    await expect(page).toHaveURL(/\/login\?next=%2F$/);
  });
}

test('the round-type panel opens fully on screen', async ({ page }) => {
  await page.goto('/');
  await logIn(page, e2ePassword('viewer'));
  await page.getByRole('button', { name: 'Round type' }).click();
  const box = await page.getByRole('group', { name: 'Round types' }).boundingBox();
  const viewportWidth = page.viewportSize()?.width ?? 0;
  expect(box).not.toBeNull();
  expect(box?.x ?? -1).toBeGreaterThanOrEqual(0);
  expect((box?.x ?? 0) + (box?.width ?? Infinity)).toBeLessThanOrEqual(viewportWidth);
});

test('a wrong password shows an error and stays on the login page', async ({ page }) => {
  await page.goto('/login');
  await logIn(page, 'definitely-not-the-password');
  await expect(page.getByRole('alert')).toHaveText('Wrong password.');
  await expect(page).toHaveURL(/\/login$/);
});

// A protocol-relative next, and one that only becomes '//evil.example' once the URL parser
// removes its dot segment ('/.//evil.example').
for (const next of ['%2F%2Fevil.example', '%2F.%2F%2Fevil.example']) {
  test(`a hostile next never leaves the site (next=${next})`, async ({ page, baseURL }) => {
    await page.goto(`/login?next=${next}`);
    await logIn(page, e2ePassword('viewer'));
    await expect(page).toHaveURL(`${baseURL ?? ''}/`);
  });
}
