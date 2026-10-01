import { expect, test } from './fixtures';

test('health answers through Caddy without a Server header', async ({ request }) => {
  const response = await request.get('/api/health');

  expect(response.status()).toBe(200);
  expect(await response.json()).toMatchObject({ status: 'ok' });
  expect(response.headers()['server']).toBeUndefined();
});

test('SPA shell renders with the security headers', async ({ page }) => {
  const response = await page.goto('/');

  const headers = response?.headers() ?? {};
  expect(headers['content-security-policy']).toContain("default-src 'self'");
  expect(headers['x-content-type-options']).toBe('nosniff');
  expect(headers['referrer-policy']).toBe('same-origin');
  expect(headers['cache-control']).toBe('no-cache');
  await expect(page.getByRole('heading', { level: 1, name: 'The Sunday Sheet' })).toBeVisible();
});

test('deep links fall back to index.html, hashed assets are immutable, missing assets 404', async ({
  page,
  request,
}) => {
  const deepLink = await request.get('/events/2026-09-13');
  expect(deepLink.status()).toBe(200);
  expect(deepLink.headers()['content-type']).toContain('text/html');
  expect(deepLink.headers()['cache-control']).toBe('no-cache');

  await page.goto('/');
  const script = await page.locator('script[type="module"]').first().getAttribute('src');
  expect(script).toMatch(/^\/assets\//);
  const asset = await request.get(script ?? '');
  expect(asset.headers()['cache-control']).toBe('public, max-age=31536000, immutable');

  // A chunk removed by a deploy must 404, never be answered with index.html cached for a year.
  const missing = await request.get('/assets/does-not-exist.js');
  expect(missing.status()).toBe(404);
  expect(missing.headers()['cache-control']).toBeUndefined();
  expect(missing.headers()['x-content-type-options']).toBe('nosniff');
  expect(missing.headers()['server']).toBeUndefined();
});

test('oversized request bodies get 413 before any route runs', async ({ request }) => {
  const upload = await request.post('/api/admin/imports', {
    data: Buffer.alloc(12 * 1024 * 1024, 1),
    headers: { 'content-type': 'application/octet-stream' },
  });
  const login = await request.post('/api/auth/login', {
    data: Buffer.alloc(300 * 1024, 1),
    headers: { 'content-type': 'application/json' },
  });

  // Both bodies declare a Content-Length over the edge limit, so Caddy refuses them before
  // proxying, with the API's own JSON envelope rather than an empty 413
  // (backend/tests/unit/api/test_edge_limits.py).
  expect(upload.status()).toBe(413);
  expect(await upload.json()).toMatchObject({ error: { code: 'payload_too_large' } });
  expect(login.status()).toBe(413);
  expect(await login.json()).toMatchObject({ error: { code: 'payload_too_large' } });
});

test.describe('the shared fixture', () => {
  test.fail('fails a test on an uncaught page error', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => {
      setTimeout(() => {
        throw new Error('deliberate uncaught error');
      }, 0);
    });
    await page.waitForTimeout(200);
  });

  test.fail('fails a test on a Content Security Policy violation', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => {
      const inline = document.createElement('script');
      inline.textContent = 'window.__inline = true;';
      document.head.append(inline);
    });
    await page.waitForTimeout(200);
  });
});

test.describe('signed out', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('an unauthenticated visit to / is sent to the login page', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/login\?next=%2F$/);
    await expect(page.getByLabel('Password')).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Main' })).toHaveCount(0);
    await expect(page.getByRole('navigation', { name: 'Tabs' })).toHaveCount(0);
  });
});
