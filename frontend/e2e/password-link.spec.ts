import type { Request } from '@playwright/test';

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

test('a doubled-slash path with p still cleans the address bar and logs in', async ({
  page,
  baseURL,
}) => {
  // page.goto('//?p=') would resolve against baseURL as a protocol-relative URL and throw.
  const origin = (baseURL ?? '').replace(/\/+$/, '');
  await page.goto(`${origin}//?p=${encodeURIComponent(e2ePassword('viewer'))}`);
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
  expect(page.url()).not.toContain('p=');
  await expect(page.getByText(/link's password didn't work/)).toHaveCount(0);
});

test('no request made while loading a password link carries the password in its Referer', async ({
  page,
}) => {
  const password = e2ePassword('viewer');
  const requests: Request[] = [];
  page.on('request', (req) => requests.push(req));
  await page.goto(`/?rt=sporting&p=${encodeURIComponent(password)}`);
  await expect(page.getByText('Filtered: Sporting')).toBeVisible();
  await page.waitForLoadState('networkidle');
  expect(requests.length).toBeGreaterThan(0);
  for (const req of requests) {
    const referer = (await req.allHeaders())['referer'] ?? '';
    expect(referer, req.url()).not.toContain(password);
    expect(referer, req.url()).not.toContain(encodeURIComponent(password));
    expect(referer, req.url()).not.toContain('p=');
  }
});
