import { request as pwRequest, type Page } from '@playwright/test';
import { ADMIN_STATE } from './authState';
import { expect, test } from './fixtures';
import { whenSettled } from './layout';

/** §3.7.5: the templates each default page must find warm. */
const PAGES: Record<string, RegExp[]> = {
  '/': [/^\/api\/insights\/home$/, /^\/api\/events\/\d{4}-\d{2}-\d{2}$/, /^\/api\/events$/],
  '/events/LATEST': [/^\/api\/insights\/sundays\/[\d-]+$/, /^\/api\/events\/[\d-]+\/achievements$/],
  '/events': [/^\/api\/events$/],
  '/stations': [/^\/api\/stations$/, /^\/api\/insights\/stations$/],
  '/club': [/^\/api\/club\/[a-z-]+$/, /^\/api\/insights\/club$/],
  '/leaderboards': [
    /^\/api\/leaderboards$/,
    /^\/api\/leaderboards\/movers$/,
    /^\/api\/insights\/leaderboards$/,
  ],
  '/race': [/^\/api\/leaderboards\/history$/],
  '/records': [/^\/api\/records$/, /^\/api\/insights\/records$/],
  '/achievements': [/^\/api\/achievements$/],
};
const NOT_WARMED = /^\/api\/club\/milestones$/; // gated: never cached

/** path + sorted query, as etag.sorted_query and warm_targets write it. */
function keyOf(raw: string): string {
  const url = new URL(raw);
  const items = [...url.searchParams.entries()].sort(([ak, av], [bk, bv]) =>
    ak === bk ? av.localeCompare(bv) : ak.localeCompare(bk),
  );
  const query = new URLSearchParams(items).toString();
  return query === '' ? url.pathname : `${url.pathname}?${query}`;
}

function record(page: Page, patterns: RegExp[]): string[] {
  const seen: string[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (request.method() !== 'GET') return;
    if (NOT_WARMED.test(url.pathname)) return;
    if (patterns.some((p) => p.test(url.pathname))) seen.push(keyOf(request.url()));
  });
  return seen;
}

test('warm targets are exactly what the SPA asks on each default page', async ({
  page,
  baseURL,
}) => {
  const admin = await pwRequest.newContext({ baseURL, storageState: ADMIN_STATE });
  const status = (await (await admin.get('/api/admin/page-cache')).json()) as { targets: string[] };
  const latest = (await (await admin.get('/api/meta')).json()) as { last_score_date: string };
  await admin.dispose();
  const targets = new Set(status.targets);
  const missing: string[] = [];
  for (const [path, patterns] of Object.entries(PAGES)) {
    const seen = record(page, patterns);
    await page.goto(path.replace('LATEST', latest.last_score_date));
    await whenSettled(page);
    page.removeAllListeners('request');
    for (const key of seen) if (!targets.has(key)) missing.push(`${path}: ${key}`);
  }
  expect(missing, 'SPA requests with no warm target (fix warm_targets, not the SPA)').toEqual([]);
});

test('Home insights come from the cache, and per-person routes never carry the header', async ({
  page,
}) => {
  await page.goto('/');
  await whenSettled(page);
  const home = await page.request.get('/api/insights/home');
  expect(home.headers()['x-page-cache']).toBe('hit');
  for (const path of ['/api/features', '/api/auth/me', '/api/bumps?keys=x']) {
    const response = await page.request.get(path);
    expect(response.headers()['x-page-cache'], path).toBeUndefined();
  }
});
