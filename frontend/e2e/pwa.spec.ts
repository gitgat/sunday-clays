import type { Page } from '@playwright/test';
import { expect, test } from './fixtures';

test.use({ serviceWorkers: 'allow' });

async function shellCaches(page: Page): Promise<Record<string, string[]>> {
  return page.evaluate(async () => {
    const out: Record<string, string[]> = {};
    for (const name of await caches.keys()) {
      if (!name.startsWith('sc-shell-')) continue;
      const keys = await (await caches.open(name)).keys();
      out[name] = keys.map((r) => new URL(r.url).pathname);
    }
    return out;
  });
}

test('manifest and worker are served with the right headers', async ({ request }) => {
  const manifest = await request.get('/manifest.webmanifest');
  expect(manifest.headers()['content-type']).toMatch(/^application\/manifest\+json/);
  const worker = await request.get('/sw.js');
  expect(worker.headers()['cache-control']).toBe('no-cache');
  expect(worker.headers()['service-worker-allowed']).toBe('/');
});

test('the worker installs a small shell and never caches /api', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
  await expect(page.locator('link[rel="manifest"]')).toHaveCount(1);
  const before = await shellCaches(page);
  expect(Object.keys(before)).toHaveLength(1);
  const [files] = Object.values(before) as [string[]];
  expect(files).toContain('/index.html');
  expect(files).toContain('/__sc-created');
  expect(files.some((f) => /^\/assets\/.+\.css$/.test(f))).toBe(true);
  const jsBefore = files.filter((f) => f.endsWith('.js')).length;
  await page.reload(); // now controlled by the worker
  await page.goto('/club');
  await expect(page.getByRole('heading', { level: 1, name: 'Club' })).toBeVisible();
  await page.goto('/events');
  await page.goto('/shooters/3');
  const after = Object.values(await shellCaches(page)).flat();
  expect(after.some((f) => f.startsWith('/api/'))).toBe(false);
  expect(after.filter((f) => f.endsWith('.js')).length).toBeGreaterThan(jsBefore); // lazy chunks at run time
});

test('logging out and loading /login keeps the registration', async ({ page, isMobile }) => {
  await page.goto('/');
  await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
  if (isMobile) await page.getByRole('button', { name: 'More' }).click();
  await page.getByRole('button', { name: 'Log out' }).click();
  await page.goto('/login');
  const count = await page.evaluate(
    async () => (await navigator.serviceWorker.getRegistrations()).length,
  );
  expect(count).toBe(1);
});

test.describe('install tip', () => {
  test.use({ installTipSeen: false });

  test('a synthetic install event shows the tip and Not now hides it for good', async ({
    page,
    isMobile,
  }) => {
    test.skip(!isMobile, 'the tip is for touch devices');
    await page.goto('/');
    await page.evaluate(() => {
      const event = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
        prompt: () => Promise.resolve(),
        userChoice: Promise.resolve({ outcome: 'dismissed' }),
      });
      window.dispatchEvent(event);
    });
    const title = page.getByRole('heading', { name: 'Add Sunday Clays to your home screen' });
    await expect(title).toBeVisible();
    await page.getByRole('button', { name: 'Not now' }).click();
    await expect(title).toHaveCount(0);
    await page.reload();
    await page.waitForTimeout(500);
    await expect(title).toHaveCount(0);
  });
});

test.describe('chunk-load recovery', () => {
  test.use({ serviceWorkers: 'block' }); // so page.route sees the chunk request

  test('a lazy chunk that fails once reloads the page once and the route renders', async ({
    page,
  }) => {
    await page.goto('/');
    let failed = false;
    await page.route(/\/assets\/ClubPage-[^/]+\.js$/, async (route) => {
      if (failed) return route.continue();
      failed = true;
      return route.fulfill({ status: 404, body: '' });
    });
    await page.goto('/club');
    await expect(page.getByRole('heading', { level: 1, name: 'Club' })).toBeVisible({
      timeout: 15_000,
    });
    expect(failed).toBe(true);
  });
});
