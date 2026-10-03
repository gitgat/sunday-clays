import type { APIRequestContext, Browser, Page } from '@playwright/test';
import { request as pwRequest } from '@playwright/test';
import { ADMIN_STATE, VIEWER_STATE } from './authState';
import { expect, test } from './fixtures';
import { whenSettled } from './layout';

// Project `admin-mutations` (one worker, after every read-only spec). Every switch a test changed is
// put back in `test.afterEach` on a fresh admin request context, so a timeout or a closed page still
// restores them. The e2e stack starts with every feature on (FEATURES_DEFAULT_ON).
test.use({ storageState: ADMIN_STATE });

/** The six launch switches. Infrastructure switches (the page cache) are never touched here. */
export const FEATURE_KEYS = [
  'link_previews',
  'tour_glossary',
  'weekly_recap',
  'pwa',
  'club_milestones',
  'summary_card',
] as const;
const SIZES = [
  { width: 390, height: 844 },
  { width: 1440, height: 900 },
] as const;
const DAY = '2026-09-27';
const FB = 'facebookexternalhit/1.1';
const GENERIC = 'Scores, trophies and stats for the Sunday Clays group at Tri-County Gun Club.';

export async function adminSwitches(api: APIRequestContext): Promise<Record<string, boolean>> {
  const response = await api.get('/api/admin/features');
  expect(response.ok()).toBe(true);
  const rows = (await response.json()) as { key: string; enabled: boolean }[];
  return Object.fromEntries(rows.map((r) => [r.key, r.enabled]));
}

export async function setSwitch(
  api: APIRequestContext,
  key: string,
  enabled: boolean,
): Promise<void> {
  const response = await api.put(`/api/admin/features/${key}`, { data: { enabled } });
  expect(response.ok(), `${key} -> ${String(enabled)}`).toBe(true);
}

export async function viewerPage(
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
  saved = await adminSwitches(request);
});

test.afterEach(async ({ baseURL }) => {
  const api = await pwRequest.newContext({ baseURL, storageState: ADMIN_STATE });
  try {
    // Only the six launch switches, and only those a test changed: a blind PUT of every row would
    // also store infrastructure switches that are meant to stay at their default.
    const now = await adminSwitches(api);
    for (const key of FEATURE_KEYS) {
      if (now[key] !== saved[key]) await setSwitch(api, key, saved[key] ?? false);
    }
  } finally {
    await api.dispose();
  }
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

test('summary card off: hidden for a viewer, 404 from its API, previewed by an admin', async ({
  page,
  request,
  browser,
}) => {
  const id = await ikeId(request);
  await setSwitch(request, 'summary_card', false);
  for (const size of SIZES) {
    const viewer = await viewerPage(browser, size);
    await viewer.goto(`/shooters/${String(id)}`);
    await whenSettled(viewer);
    await expect(viewer.getByRole('heading', { name: /Summary card/ })).toHaveCount(0);
    const api = await viewer.request.get(`/api/shooters/${String(id)}/summary?to=${DAY}`);
    expect(api.status()).toBe(404);
    await viewer.context().close();
  }
  await page.goto(`/shooters/${String(id)}`);
  const card = page.getByRole('region', { name: /^Summary card/ });
  await expect(card).toBeVisible();
  await expect(card.getByText('Admin preview')).toBeVisible();
});

test('link previews off: every crawler gets the generic preview', async ({ request }) => {
  await setSwitch(request, 'link_previews', false);
  expect(await description(request)).toBe(GENERIC);
});

test('glossary off: "Page not found" and no nav item for a viewer', async ({
  request,
  browser,
}) => {
  await setSwitch(request, 'tour_glossary', false);
  for (const size of SIZES) {
    const viewer = await viewerPage(browser, size);
    await viewer.goto('/glossary');
    await expect(viewer.getByRole('heading', { name: 'Page not found' })).toBeVisible();
    await viewer.goto('/');
    if (size.width < 600) await viewer.getByRole('button', { name: 'More' }).click();
    await expect(viewer.getByRole('link', { name: 'Glossary' })).toHaveCount(0);
    await viewer.context().close();
  }
});

const TIP = 'Add Sunday Clays to your home screen';
/** Home's cards for a first-time viewer at the plan's base (R7: nothing is removed from Home). */
const HOME_CARDS = ['Latest Sunday', 'Club pulse', 'Insights', 'Which one are you?'] as const;

async function fireInstallPrompt(viewer: Page): Promise<void> {
  await viewer.evaluate(() => {
    const event = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
      prompt: () => Promise.resolve(),
      userChoice: Promise.resolve({ outcome: 'dismissed' }),
    });
    window.dispatchEvent(event);
  });
}

test("all switches off (the production default): the viewer sees today's app", async ({
  request,
  browser,
}) => {
  const id = await ikeId(request);
  // Positive control, same setup: only `pwa` on, a first-time phone viewer, the event fired after
  // the page settles (lib/installPrompt.ts listens from import). The tip shows, so its absence
  // below is the switch, not a missed event.
  for (const key of FEATURE_KEYS) await setSwitch(request, key, key === 'pwa');
  const control = await viewerPage(browser, SIZES[0]);
  await control.goto('/');
  await whenSettled(control);
  await fireInstallPrompt(control);
  await expect(control.getByRole('heading', { name: TIP })).toBeVisible();
  await control.context().close();

  await setSwitch(request, 'pwa', false);
  for (const size of SIZES) {
    const viewer = await viewerPage(browser, size);
    // As a first-time visitor: no tour done, no tip dismissed.
    await viewer.goto('/');
    await whenSettled(viewer);
    await fireInstallPrompt(viewer);
    await viewer.waitForTimeout(2000); // past the tour's 1.5 s wait
    await expect(viewer.getByRole('dialog')).toHaveCount(0);
    await expect(viewer.getByRole('heading', { name: /^Club milestone/ })).toHaveCount(0);
    // The tip is for touch devices, so only the 390 run (with its positive control) proves "off".
    await expect(viewer.getByRole('heading', { name: TIP })).toHaveCount(0);
    await expect(viewer.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toBeVisible();
    for (const name of HOME_CARDS) {
      await expect(viewer.getByRole('heading', { name, exact: true }), name).toBeVisible();
    }
    await expect(viewer.getByText('Turnout per Sunday', { exact: true })).toBeVisible();
    if (size.width < 600) await viewer.getByRole('button', { name: 'More' }).click();
    await expect(viewer.getByRole('link', { name: 'Glossary' })).toHaveCount(0);

    await viewer.goto(`/shooters/${String(id)}`);
    await whenSettled(viewer);
    await expect(viewer.getByText('Summary card')).toHaveCount(0); // no title leak
    await viewer.goto('/club');
    await whenSettled(viewer);
    await expect(viewer.getByRole('heading', { name: /^Milestones/ })).toHaveCount(0);
    await viewer.goto('/glossary');
    await expect(viewer.getByRole('heading', { name: 'Page not found' })).toBeVisible();

    await viewer.goto('/about');
    await whenSettled(viewer);
    await expect(
      viewer.getByRole('region', { name: 'Your privacy' }).getByRole('listitem'),
    ).toHaveCount(5); // the link-preview sentence is behind its switch

    const features = await viewer.request.get('/api/features');
    expect(await features.json()).toEqual({ switches: {} });
    await viewer.context().close();
  }
  expect(await description(request)).toBe(GENERIC);
  expect((await request.get(`/api/og/image/sunday/${DAY}.png`)).status()).toBe(404);
});
