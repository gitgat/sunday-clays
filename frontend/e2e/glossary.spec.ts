import { expect, test } from './fixtures';

test('a hash link scrolls to its term', async ({ page }) => {
  await page.goto('/glossary#percentile');
  await expect(page.getByRole('heading', { level: 1, name: 'Glossary' })).toBeVisible();
  await expect(page.locator('dt#percentile')).toBeInViewport();
});

test('an explainer on a profile links to the glossary', async ({ page }) => {
  await page.goto('/shooters/3');
  // Charts load lazily and swap in: open an explainer only once the page has settled.
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page.getByRole('status', { name: 'Loading charts' })).toHaveCount(0);
  const about = page.getByRole('button', { name: 'About this chart' }).first();
  await about.click();
  const words = page.getByText('Words used here:').first();
  await expect(words).toBeVisible();
  const link = words.locator('xpath=..').getByRole('link').first();
  const href = (await link.getAttribute('href')) ?? '';
  expect(href).toMatch(/^\/glossary#[a-z-]+$/);
  await link.click();
  await expect(page.getByRole('heading', { level: 1, name: 'Glossary' })).toBeVisible();
  const url = new URL(page.url());
  expect(url.pathname + url.hash).toBe(href);
});

test('the nav lists Glossary', async ({ page, isMobile }) => {
  await page.goto('/');
  if (isMobile) await page.getByRole('button', { name: 'More' }).click();
  await expect(page.getByRole('link', { name: 'Glossary' })).toBeVisible();
});
