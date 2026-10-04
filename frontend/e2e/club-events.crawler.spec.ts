import { request as pwRequest } from '@playwright/test';
import { expect, test } from './fixtures';

// D24/D25: a crawler on a club-events path gets Plan 19's generic club preview (no title, date,
// count or name), and the club-events API still needs a session (401 before the launch gate).
test('a crawler gets the generic club preview for a club event, never its details', async ({
  baseURL,
}) => {
  const crawler = await pwRequest.newContext({
    baseURL,
    // The project's viewer session would otherwise be inherited: a crawler has none.
    storageState: { cookies: [], origins: [] },
    extraHTTPHeaders: { 'User-Agent': 'facebookexternalhit/1.1' },
  });
  try {
    const page = await crawler.get('/club-events/1');
    expect(page.status()).toBe(200);
    const html = await page.text();
    expect(html).toMatch(/<meta property="og:title" content="Sunday Clays · Tri-County Gun Club"/);
    expect(html).not.toMatch(/Fall Fun Shoot|Hadley|Quill|signed up|going/i);
    const data = await crawler.get('/api/club-events');
    expect(data.status(), await data.text()).toBe(401);
    expect(((await data.json()) as { error: { code: string } }).error.code).toBe('unauthenticated');
  } finally {
    await crawler.dispose();
  }
});
