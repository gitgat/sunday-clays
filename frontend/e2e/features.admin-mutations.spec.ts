import type { APIRequestContext, Browser, Page } from '@playwright/test';
import { request as pwRequest } from '@playwright/test';
import { ADMIN_STATE, VIEWER_STATE } from './authState';
import { expect, test } from './fixtures';
import { whenSettled } from './layout';

// Project `admin-mutations` (one worker, after every read-only spec). Every switch a test changed is
// put back in `test.afterEach` on a fresh admin request context, so a timeout or a closed page still
// restores them. The e2e stack starts with every Plan 19 launch switch on (FEATURES_DEFAULT_ON);
// `events` starts off.
test.use({ storageState: ADMIN_STATE });

/**
 * Plan 19's six launch switches. The Plan 20 `events` switch stays off on the e2e stack and is
 * left out on purpose: the all-off test expects no stored switches, and
 * club-events.admin-mutations.spec.ts restores `events` itself.
 */
const FEATURE_KEYS = [
  'link_previews',
  'tour_glossary',
  'weekly_recap',
  'pwa',
  'club_milestones',
  'summary_card',
] as const;
/** Put back in afterEach when a test flipped it (the page cache test does), even if that test fails. */
const RESTORED_KEYS = [...FEATURE_KEYS, 'page_cache'] as const;
const SIZES = [
  { width: 390, height: 844 },
  { width: 1440, height: 900 },
] as const;
const DAY = '2026-09-27';
const FB = 'facebookexternalhit/1.1';
const GENERIC = 'Scores, trophies and stats for the Sunday Clays group at Tri-County Gun Club.';

async function adminSwitches(api: APIRequestContext): Promise<Record<string, boolean>> {
  const response = await api.get('/api/admin/features');
  expect(response.ok()).toBe(true);
  const rows = (await response.json()) as { key: string; enabled: boolean }[];
  return Object.fromEntries(rows.map((r) => [r.key, r.enabled]));
}

async function setSwitch(api: APIRequestContext, key: string, enabled: boolean): Promise<void> {
  const response = await api.put(`/api/admin/features/${key}`, { data: { enabled } });
  expect(response.ok(), `${key} -> ${String(enabled)}`).toBe(true);
}

async function viewerPage(
  browser: Browser,
  size: { width: number; height: number },
): Promise<Page> {
  const context = await browser.newContext({
    storageState: VIEWER_STATE,
    viewport: size,
    isMobile: size.width < 600,
    hasTouch: size.width < 600,
    serviceWorkers: 'block',
  });
  return context.newPage();
}

let saved: Record<string, boolean> = {};

test.beforeEach(async ({ request }) => {
  saved = {};
  saved = await adminSwitches(request);
});

test.afterEach(async ({ baseURL }) => {
  const api = await pwRequest.newContext({ baseURL, storageState: ADMIN_STATE });
  const failures: string[] = [];
  try {
    // Only Plan 19's six launch switches (not `events`, which stays off here) and the page cache,
    // only those recorded in beforeEach, and only those a test changed: a blind PUT of every row
    // would also store infrastructure switches that are meant to stay at their default. Each key
    // gets its own attempt.
    // If the current values cannot be read, nothing can be confirmed as changed: restore nothing
    // blindly (a blind PUT of page_cache would clear the cache and its last warm-up), fail once.
    let now: Record<string, boolean> | null = null;
    try {
      now = await adminSwitches(api);
    } catch {
      failures.push('(could not read the current switches)');
    }
    for (const key of RESTORED_KEYS) {
      const was = saved[key];
      if (now === null || was === undefined || now[key] === was) continue;
      try {
        await setSwitch(api, key, was);
      } catch {
        failures.push(key);
      }
    }
  } finally {
    await api.dispose();
  }
  if (failures.length > 0) throw new Error(`could not restore switches: ${failures.join(', ')}`);
});

async function description(api: APIRequestContext): Promise<string | null> {
  const html = await (await api.get(`/events/${DAY}`, { headers: { 'User-Agent': FB } })).text();
  return /property="og:description" content="([^"]*)"/.exec(html)?.[1] ?? null;
}

// An active shooter by name, looked up through the API (ids differ between databases).
async function ikeId(api: APIRequestContext): Promise<number> {
  const response = await api.get('/api/shooters?q=Hadley');
  expect(response.ok()).toBe(true);
  const rows = (await response.json()) as { shooter_id: number; display_name: string }[];
  const found = rows.find((r) => r.display_name === 'Hadley, Ike');
  expect(found, 'Hadley, Ike in the seed').toBeDefined();
  return found?.shooter_id ?? 0;
}

const SUMMARY = (page: Page) => page.getByRole('region', { name: /^Summary card/ });
const BADGE = 'Admin preview';

async function openGlossaryNav(viewer: Page, size: { width: number }): Promise<void> {
  if (size.width < 600) await viewer.getByRole('button', { name: 'More' }).click();
}

test('summary card off: hidden for a viewer, 404 from its API, previewed by an admin', async ({
  page,
  request,
  browser,
}) => {
  const id = await ikeId(request);
  const url = `/api/shooters/${String(id)}/summary?to=${DAY}`;
  await setSwitch(request, 'summary_card', false);
  expect((await request.get(url)).status()).toBe(200); // the admin gets the same URL
  for (const size of SIZES) {
    const viewer = await viewerPage(browser, size);
    await viewer.goto(`/shooters/${String(id)}`);
    await whenSettled(viewer);
    await expect(SUMMARY(viewer)).toHaveCount(0);
    expect((await viewer.request.get(url)).status()).toBe(404);
    await viewer.context().close();
  }
  await page.goto(`/shooters/${String(id)}`);
  await expect(SUMMARY(page)).toBeVisible();
  await expect(SUMMARY(page).getByText(BADGE)).toBeVisible();
});

test('link previews off: every crawler gets the generic preview', async ({ request }) => {
  // On first (the stack starts with every switch on): the Sunday's facts and its image.
  expect(await description(request)).toMatch(/^Sunday, Sep 27, 2026 · /);
  expect((await request.get(`/api/og/image/sunday/${DAY}.png`)).status()).toBe(200);
  await setSwitch(request, 'link_previews', false);
  expect(await description(request)).toBe(GENERIC);
  expect((await request.get(`/api/og/image/sunday/${DAY}.png`)).status()).toBe(404);
});

test('glossary off: "Page not found" and no nav item for a viewer', async ({
  request,
  browser,
}) => {
  for (const on of [true, false]) {
    if (!on) await setSwitch(request, 'tour_glossary', false);
    for (const size of SIZES) {
      const viewer = await viewerPage(browser, size);
      await viewer.goto('/glossary');
      await expect(viewer.getByRole('heading', { level: 1, name: 'Glossary' })).toHaveCount(
        on ? 1 : 0,
      );
      await expect(viewer.getByRole('heading', { name: 'Page not found' })).toHaveCount(on ? 0 : 1);
      await viewer.goto('/');
      await openGlossaryNav(viewer, size);
      await expect(viewer.getByRole('link', { name: 'Glossary' })).toHaveCount(on ? 1 : 0);
      await viewer.context().close();
    }
  }
});

const TIP = 'Add Sunday Clays to your home screen';

async function fireInstallPrompt(viewer: Page): Promise<void> {
  await viewer.evaluate(() => {
    const event = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
      prompt: () => Promise.resolve(),
      userChoice: Promise.resolve({ outcome: 'dismissed' }),
    });
    window.dispatchEvent(event);
  });
}

/**
 * Every gated surface, for a first-time visitor. `on`: each is present (the control that proves
 * the locators still match); otherwise each is absent. `admin`: the page is the admin's, so each
 * is present while off, with the preview badge.
 */
async function checkViewer(
  page: Page,
  size: { width: number },
  id: number,
  on: boolean,
  admin = false,
): Promise<void> {
  const shown = on || admin;
  const count = shown ? 1 : 0;
  await page.goto('/');
  await whenSettled(page);
  const dialog = page.getByRole('dialog');
  if (shown) await expect(dialog).toBeVisible();
  else await page.waitForTimeout(2000); // past the tour's 1.5 s wait
  await expect(dialog).toHaveCount(count);
  if (shown) {
    if (admin) await expect(dialog.getByText(BADGE)).toBeVisible();
    await dialog.getByRole('button', { name: 'Skip tour' }).click();
    await expect(dialog).toHaveCount(0);
  }
  const milestone = page.getByRole('heading', { name: /^Club milestone/ });
  await expect(milestone).toHaveCount(count);
  if (admin) await expect(milestone.getByText(BADGE)).toBeVisible();
  await expect(page.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toBeVisible();
  await expect(page.getByText('Turnout per Sunday', { exact: true })).toBeVisible();
  await openGlossaryNav(page, size);
  await expect(page.getByRole('link', { name: 'Glossary' })).toHaveCount(count);

  await page.goto(`/shooters/${String(id)}`);
  await whenSettled(page);
  await expect(SUMMARY(page)).toHaveCount(count);
  if (!shown) await expect(page.getByText('Summary card')).toHaveCount(0); // no title leak
  if (admin) await expect(SUMMARY(page).getByText(BADGE)).toBeVisible();

  await page.goto('/club');
  await whenSettled(page);
  const milestones = page.getByRole('heading', { name: /^Milestones/ });
  await expect(milestones).toHaveCount(count);
  if (admin) await expect(page.locator('#milestones').getByText(BADGE)).toBeVisible();

  await page.goto('/glossary');
  await expect(page.getByRole('heading', { level: 1, name: 'Glossary' })).toHaveCount(count);
  await expect(page.getByRole('heading', { name: 'Page not found' })).toHaveCount(1 - count);
  if (admin) await expect(page.getByText(BADGE)).toBeVisible();

  await page.goto('/about');
  await whenSettled(page);
  const items = page.getByRole('region', { name: 'Your privacy' }).getByRole('listitem');
  await expect(items).toHaveCount(on || admin ? 6 : 5); // the link-preview sentence
  if (admin) await expect(items.getByText(BADGE)).toBeVisible();
}

// One test per size: a flip empties nothing, but every page load after one is cold (the page cache
// recomputes), and a single test doing all sixteen loads at both sizes outgrew the default 30 s on
// a slow CI runner (14 placeholders still up after 15 s). Each size has its own on-state control.
for (const size of SIZES) {
  test(`all switches off (the production default) at ${String(size.width)}: the viewer sees today's app`, async ({
    request,
    browser,
  }) => {
    test.setTimeout(120_000);
    const id = await ikeId(request);
    // Control: every switch on (the stack's start). The same checks must find every surface.
    for (const key of FEATURE_KEYS) await setSwitch(request, key, true);
    const on = await viewerPage(browser, size);
    await checkViewer(on, size, id, true);
    await on.context().close();

    if (size.width < 600) {
      // Control for the install tip: only `pwa` on, a first-time phone viewer, the event fired
      // after the page settles (lib/installPrompt.ts listens from import). The tip shows, so its
      // absence below is the switch, not a missed event. The tip is for touch devices, so only
      // the phone run proves "off".
      for (const key of FEATURE_KEYS) await setSwitch(request, key, key === 'pwa');
      const control = await viewerPage(browser, size);
      await control.goto('/');
      await whenSettled(control);
      await fireInstallPrompt(control);
      await expect(control.getByRole('heading', { name: TIP })).toBeVisible();
      await control.context().close();
    }

    for (const key of FEATURE_KEYS) await setSwitch(request, key, false);
    const viewer = await viewerPage(browser, size);
    await checkViewer(viewer, size, id, false);
    if (size.width < 600) {
      await viewer.goto('/');
      await whenSettled(viewer);
      await fireInstallPrompt(viewer);
      await expect(viewer.getByRole('heading', { name: TIP })).toHaveCount(0);
    }
    const features = await viewer.request.get('/api/features');
    expect(await features.json()).toEqual({ switches: {} });
    await viewer.context().close();

    // The admin, in a fresh context, still sees every surface, marked as a preview.
    const adminContext = await browser.newContext({
      storageState: ADMIN_STATE,
      viewport: size,
      isMobile: size.width < 600,
      hasTouch: size.width < 600,
      serviceWorkers: 'block',
    });
    await checkViewer(await adminContext.newPage(), size, id, false, true);
    await adminContext.close();

    expect(await description(request)).toBe(GENERIC);
    expect((await request.get(`/api/og/image/sunday/${DAY}.png`)).status()).toBe(404);
  });
}

test('page cache off: viewers get the same Home, computed live; on again in afterEach', async ({
  page,
  request,
  browser,
}) => {
  const first = await viewerPage(browser, SIZES[1]);
  const before = await first.request.get('/api/insights/home');
  expect(before.status()).toBe(200);
  const beforeBody = await before.text();
  await first.context().close();
  await setSwitch(request, 'page_cache', false);
  for (const size of SIZES) {
    const viewer = await viewerPage(browser, size);
    await viewer.goto('/');
    await whenSettled(viewer);
    await expect(viewer.getByRole('heading', { name: 'Latest Sunday', exact: true })).toBeVisible();
    const home = await viewer.request.get('/api/insights/home');
    expect(home.status()).toBe(200);
    expect(home.headers()['x-page-cache']).toBe('bypass');
    expect(await home.text()).toBe(beforeBody);
    await viewer.context().close();
  }
  await page.goto('/admin/features');
  const infra = page.getByRole('region', { name: 'Infrastructure' });
  await expect(infra.getByRole('switch', { name: 'Page cache' })).toHaveAttribute(
    'aria-checked',
    'false',
  );
  await expect(infra.getByText('Admin preview')).toHaveCount(0);
});
