import {
  request as pwRequest,
  type APIRequestContext,
  type APIResponse,
  type Browser,
  type BrowserContext,
  type Locator,
  type Page,
} from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { ADMIN_STATE, VIEWER_STATE } from './authState';
import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';
import {
  CANCELLED,
  EMPTY_ROSTER,
  PROMOTED,
  SWITCHED_OFF,
  WAITLIST_WARNING,
} from '../src/features/club-events/format';

// Project `admin-mutations` (one worker, after every read-only spec). It turns the `events`
// switch on and creates "Fall Fun Shoot"; `beforeEach` and `afterEach`, each on a fresh admin
// request context, delete every event with that title, delete Hadley's email on file (a 404 is
// fine) and turn the switch off, so a run that died half-way never leaves the next one with an
// email on file (which would turn step 3 into "We'll use the email we have for you.").
test.use({ storageState: ADMIN_STATE });

const TITLE = 'Fall Fun Shoot';
const IKE_EMAIL = 'ike.hadley@example.com';
const DANA_EMAIL = 'dana.quill@example.com';
const LONG_NAME = 'Marigold Fairweather-Ashcombe Montgomery-Quillington Riverly'; // 60 characters
const NOTES = `Bring eye and ear protection.\nDirections: https://example.com/${'a'.repeat(100)}`;
const PHONE = { width: 390, height: 844 } as const;
const VIEWPORTS = [PHONE, { width: 1440, height: 900 }] as const;
const SLOW = { timeout: 15_000 };

type Shooter = { shooter_id: number; display_name: string };
type AdminEvent = { id: number; title: string };

/** Today's date in club time plus `days`, as YYYY-MM-DD (never a fixed date). */
function clubDate(days: number): string {
  const today = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Los_Angeles',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
  const [year = 1970, month = 1, day = 1] = today.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10);
}

async function hadleyId(api: APIRequestContext): Promise<number> {
  const found = (await (await api.get('/api/shooters?q=Hadley')).json()) as Shooter[];
  const hadley = found.find((s) => s.display_name === 'Hadley, Ike');
  if (hadley === undefined) throw new Error('Hadley, Ike is missing from the e2e seed');
  return hadley.shooter_id;
}

async function cleanUp(baseURL: string | undefined): Promise<void> {
  const api = await pwRequest.newContext({ baseURL, storageState: ADMIN_STATE });
  try {
    // The switch comes off first, so a failure in the deletes below can never leave it on.
    const off = await api.put('/api/admin/features/events', { data: { enabled: false } });
    expect(off.ok(), 'turn the events switch off').toBe(true);
    const events = (await (await api.get('/api/admin/club-events')).json()) as AdminEvent[];
    for (const event of events.filter((e) => e.title === TITLE)) {
      const gone = await api.delete(`/api/admin/club-events/${event.id}`);
      expect(gone.status(), `delete club event ${event.id}`).toBe(204);
    }
    // 204 when an email was on file, 404 when there was none.
    const contact = await api.delete(`/api/admin/shooter-contacts/${await hadleyId(api)}`);
    expect([204, 404], 'delete the email on file for Hadley').toContain(contact.status());
  } finally {
    await api.dispose();
  }
}

test.beforeEach(async ({ baseURL }) => {
  await cleanUp(baseURL);
});

test.afterEach(async ({ baseURL }) => {
  await cleanUp(baseURL);
});

/** A member's browser (a phone by default): a fresh context with the viewer session, recording every club-event body. */
async function member(
  browser: Browser,
  baseURL: string | undefined,
  bodies: Promise<string>[],
  viewport: { width: number; height: number } = PHONE,
): Promise<{ context: BrowserContext; page: Page }> {
  // Plan 19's `viewerPage` options (touch on a phone, service workers blocked so page.route and
  // fresh assets work) plus the `tourSeen`/`installTipSeen` marks, which the `test` fixtures give
  // only the test's own `page`. Without them the first-visit tour (tour_glossary is on in the e2e
  // stack) opens over the Coming up card on viewer A's Home.
  const context = await browser.newContext({
    baseURL,
    storageState: VIEWER_STATE,
    viewport,
    isMobile: viewport.width < 600,
    hasTouch: viewport.width < 600,
    serviceWorkers: 'block',
  });
  await context.addInitScript(() => {
    try {
      localStorage.setItem('sc.tour.v1', 'done');
      localStorage.setItem('sc.install.dismissed', '1');
    } catch {
      // storage blocked: the member meets the tour, as a real visitor would
    }
  });
  const page = await context.newPage();
  page.on('response', (response) => {
    if (new URL(response.url()).pathname.startsWith('/api/club-events')) {
      bodies.push(response.text().catch(() => ''));
    }
  });
  return { context, page };
}

/** An element's top edge from the top of the page (scrolling does not change it). */
function pageTop(locator: Locator): Promise<number> {
  return locator.evaluate((el) => Math.round(el.getBoundingClientRect().top + window.scrollY));
}

/** The top edge once two reads half a second apart agree. */
async function settledTop(locator: Locator): Promise<number> {
  let last = -1;
  await expect
    .poll(
      async () => {
        const now = await pageTop(locator);
        const still = now === last;
        last = now;
        return still;
      },
      { intervals: [500], timeout: 15_000, message: 'the page never stopped moving' },
    )
    .toBe(true);
  return last;
}

async function openSheet(page: Page, eventId: number): Promise<ReturnType<Page['getByRole']>> {
  await page.goto(`/club-events/${eventId}`);
  await page.getByRole('button', { name: 'Sign up', exact: true }).click();
  return page.getByRole('dialog', { name: 'Sign up' });
}

test('club events end to end: prepare, launch, sign up, waitlist, cancel, export', async ({
  page,
  browser,
  baseURL,
}) => {
  test.setTimeout(300_000);
  const bodies: Promise<string>[] = [];

  // 1. The admin sees the page and its badge while the switch is off.
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/club-events');
  await expect(page.getByRole('heading', { level: 1, name: 'Club events' })).toBeVisible();
  await expect(page.getByText('Admin preview').first()).toBeVisible();
  // Decision 24: in preview an admin's nav holds both links, under two different names.
  const mainNav = page.getByRole('navigation', { name: 'Main' });
  await expect(mainNav.getByRole('link', { name: 'Club events', exact: true })).toHaveAttribute(
    'href',
    '/club-events',
  );
  await expect(
    mainNav.getByRole('link', { name: 'Manage club events', exact: true }),
  ).toHaveAttribute('href', '/admin/club-events');

  // 2. The admin creates the event 14 days from today (club time), then turns the switch on.
  await page.goto('/admin/club-events');
  await page.getByRole('button', { name: 'New event' }).click();
  await page.getByLabel('Title', { exact: true }).fill(TITLE);
  await page.getByLabel('Date', { exact: true }).fill(clubDate(14));
  await page.getByLabel('Start time', { exact: true }).fill('10:00');
  await expect(page.getByLabel('Deadline time', { exact: true })).toHaveValue('20:00');
  await page.getByLabel('Notes', { exact: true }).fill(NOTES);
  await page.getByLabel('Capacity', { exact: true }).fill('2');
  await page.getByRole('switch', { name: 'Guests allowed' }).click();
  await page.getByLabel('Most guests each', { exact: true }).fill('1');
  await page.getByRole('button', { name: 'Create event' }).click();
  await expect(page.getByRole('button', { name: new RegExp(TITLE) })).toBeVisible(SLOW);
  const events = (await (await page.request.get('/api/admin/club-events')).json()) as AdminEvent[];
  const eventId = events.find((e) => e.title === TITLE)?.id;
  expect(eventId, 'the new event in the admin list').toBeDefined();
  const id = eventId as number;
  await page.goto('/admin/features');
  const toggle = page.getByRole('switch', { name: 'Club events' });
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-checked', 'true');

  // 3. Viewer A: Home's "Coming up" card, then a sign-up as Hadley, Ike with one guest.
  const a = await member(browser, baseURL, bodies);
  await a.page.goto('/');
  const card = a.page.getByRole('region', { name: 'Coming up' });
  await expect(card).toContainText(TITLE, SLOW);
  await card.getByRole('link', { name: 'Sign up' }).click();
  await expect(a.page).toHaveURL(new RegExp(`/club-events/${id}$`));
  await a.page.getByRole('button', { name: 'Sign up', exact: true }).click();
  const sheetA = a.page.getByRole('dialog', { name: 'Sign up' });
  await sheetA.getByRole('searchbox', { name: 'Who are you?' }).fill('hadley');
  await sheetA.getByRole('button', { name: 'Hadley, Ike', exact: true }).click();
  await sheetA.getByLabel('Your email').fill(IKE_EMAIL);
  await sheetA.getByRole('button', { name: 'More guests' }).click();
  await sheetA.getByRole('button', { name: 'Sign me up' }).click();
  // The status box and the screen-reader announcer both say it; check the box.
  const mine = (page: Page) => page.getByRole('region', { name: 'Your sign-up' });
  await expect(mine(a.page).getByText("You're in, plus 1 guest. See you there!")).toBeVisible(SLOW);

  // 4. Viewer B: "I'm not listed" as Dana Quill: the event is full, so the waitlist.
  const b = await member(browser, baseURL, bodies);
  const sheetB = await openSheet(b.page, id);
  await sheetB.getByRole('button', { name: "I'm not listed" }).click();
  await sheetB.getByLabel('Your first and last name').fill('Dana Quill');
  await sheetB.getByLabel('Your email').fill(DANA_EMAIL);
  await expect(sheetB.getByText(WAITLIST_WARNING)).toBeVisible();
  await sheetB.getByRole('button', { name: 'Sign me up' }).click();
  await expect(
    mine(b.page).getByText(
      "You're on the waitlist: #1. If a spot opens, you move up automatically.",
    ),
  ).toBeVisible(SLOW);

  // 9 (moved, Decision 1). The admin roster shows both emails; the CSV has the §5.5 header; the
  // audit log on the Ops page shows the export.
  await page.goto('/admin/club-events');
  await page.getByRole('button', { name: new RegExp(TITLE) }).click();
  await expect(page.getByText(IKE_EMAIL)).toBeVisible(SLOW);
  await expect(page.getByText(DANA_EMAIL)).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Export CSV' }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(
    new RegExp(`^club-event-${id}-\\d{4}-\\d{2}-\\d{2}-roster\\.csv$`),
  );
  const csv = await readFile((await download.path()) ?? '', 'utf-8');
  expect(csv.split('\r\n')[0]).toBe(
    'status,waitlist_position,name,shooter_id,email,guests,spots,signed_up_local',
  );
  await page.goto('/admin/ops');
  await expect(
    page.getByRole('table', { name: 'Audit log' }).getByText('club_events.roster_export').first(),
  ).toBeVisible(SLOW);

  // 5. Viewer C: a typed name that is on the shooter list is refused.
  const c = await member(browser, baseURL, bodies);
  const sheetC = await openSheet(c.page, id);
  await sheetC.getByRole('button', { name: "I'm not listed" }).click();
  await sheetC.getByLabel('Your first and last name').fill('Ike Hadley');
  await sheetC.getByLabel('Your email').fill('someone@example.com');
  await sheetC.getByRole('button', { name: 'Sign me up' }).click();
  await expect(sheetC.getByRole('alert')).toContainText('That name is already on the shooter list');
  await sheetC.getByRole('button', { name: 'Close' }).click();

  // 6. Viewer A cancels from the same phone; B's next load says the spot opened.
  await a.page.getByRole('button', { name: 'Cancel my spot' }).click();
  await a.page.getByRole('dialog').getByRole('button', { name: 'Cancel my spot' }).click();
  await expect(a.page.getByRole('button', { name: 'Sign up', exact: true })).toBeVisible(SLOW);
  await b.page.reload();
  await expect(b.page.getByText(PROMOTED)).toBeVisible(SLOW);

  // 7. Viewer C cancels Dana's spot by email: a wrong one first, then the right one.
  await c.page.reload();
  await c.page.getByRole('button', { name: "Cancel Dana Quill's spot" }).click();
  const cancelSheet = c.page.getByRole('dialog', { name: "Cancel Dana Quill's spot" });
  await cancelSheet.getByLabel('Type the email used for this sign-up.').fill('wrong@example.com');
  await cancelSheet.getByRole('button', { name: 'Cancel spot' }).click();
  await expect(cancelSheet.getByRole('alert')).toHaveText(
    "That email doesn't match this sign-up. Check it and try again.",
  );
  await cancelSheet.getByLabel('Type the email used for this sign-up.').fill(DANA_EMAIL);
  await cancelSheet.getByRole('button', { name: 'Cancel spot' }).click();
  await expect(cancelSheet).toHaveCount(0, SLOW);
  // The announcer names the cancelled spot; the roster row (the exact name) is gone.
  await expect(c.page.getByTestId('club-event-announcer')).toHaveText(
    "Dana Quill's spot was cancelled.",
    SLOW,
  );
  await expect(c.page.getByText('Dana Quill', { exact: true })).toHaveCount(0, SLOW);

  // Review Focus 5: a 60-character typed name on a phone.
  const d = await member(browser, baseURL, bodies);
  const sheetD = await openSheet(d.page, id);
  await sheetD.getByRole('button', { name: "I'm not listed" }).click();
  await sheetD.getByLabel('Your first and last name').fill(LONG_NAME);
  await sheetD.getByLabel('Your email').fill('marigold@example.com');
  await sheetD.getByRole('button', { name: 'Sign me up' }).click();
  await expect(d.page.getByText(LONG_NAME)).toBeVisible(SLOW);
  await expectNoSideScroll(d.page);

  // 8. No club-event response a member received holds an email.
  const texts = await Promise.all(bodies);
  expect(texts.length).toBeGreaterThan(10);
  for (const text of texts) expect(text).not.toContain('@');

  // The About page's privacy lines follow the switch: on now, so a member reads them.
  await a.page.goto('/about');
  const privacy = a.page.getByRole('region', { name: 'Your privacy' });
  await expect(privacy.getByText(/If you sign up for a club event/)).toBeVisible(SLOW);
  await expect(privacy.getByText(/Only organizers see emails/)).toBeVisible();

  // 10 and 11. Every page at both sizes: no sideways scroll; on Home, "Coming up" is below Next
  // Sunday, and Next Sunday does not move when the club-event list arrives.
  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport);
    for (const path of ['/club-events', `/club-events/${id}`, '/about']) {
      await page.goto(path);
      await whenSettled(page);
      await expectNoSideScroll(page);
    }
    // The organizer page with its editor open (the roster: a table at 1440, stacked rows at 390)
    // and the Contacts tab (the same), §7.3 and §7.4: never a sideways scroll.
    await page.goto('/admin/club-events');
    await whenSettled(page);
    await expectNoSideScroll(page);
    await page.getByRole('button', { name: new RegExp(TITLE) }).click();
    await expect(page.getByText('marigold@example.com')).toBeVisible(SLOW);
    await expectNoSideScroll(page);
    await page.getByRole('tab', { name: 'Contacts' }).click();
    await expect(page.getByText(IKE_EMAIL)).toBeVisible(SLOW);
    await expectNoSideScroll(page);
    let release: () => void = () => undefined;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route('**/api/club-events', async (route) => {
      await held;
      await route.continue();
    });
    await page.goto('/');
    await whenSettled(page);
    const nextSunday = page.getByRole('region', { name: 'Next Sunday', exact: true });
    // Widgets above Next Sunday may still be growing: wait for its page position to hold still
    // before the club-event list is let through, so only that list can move it.
    const before = await settledTop(nextSunday);
    release();
    const comingUp = page.getByRole('region', { name: 'Coming up' });
    await expect(comingUp).toBeVisible(SLOW);
    // The card's insertion is the only thing that could shift Next Sunday, and it is in already.
    const after = await pageTop(nextSunday);
    const below = await pageTop(comingUp);
    expect(after, `Next Sunday moved at ${viewport.width}px`).toBe(before);
    expect(below, `Coming up below Next Sunday at ${viewport.width}px`).toBeGreaterThan(after);
    await page.unroute('**/api/club-events');
    await expectNoSideScroll(page);
  }

  for (const m of [a, b, c, d]) await m.context.close();
});

type Api = APIRequestContext;

async function withApi<T>(
  baseURL: string | undefined,
  state: string,
  run: (api: Api) => Promise<T>,
): Promise<T> {
  const api = await pwRequest.newContext({ baseURL, storageState: state });
  try {
    return await run(api);
  } finally {
    await api.dispose();
  }
}

async function ok(response: APIResponse, what: string): Promise<void> {
  expect(response.ok(), `${what}: ${response.status()} ${await response.text()}`).toBe(true);
}

/** An open event ("Fall Fun Shoot", 14 days out) with the switch on, made through the API. */
async function seedEvent(baseURL: string | undefined, capacity: number | null): Promise<number> {
  return withApi(baseURL, ADMIN_STATE, async (api) => {
    await ok(await api.put('/api/admin/features/events', { data: { enabled: true } }), 'switch on');
    const created = await api.post('/api/admin/club-events', {
      data: {
        title: TITLE,
        starts_local: `${clubDate(14)}T10:00`,
        deadline_local: `${clubDate(13)}T20:00`,
        notes: NOTES,
        capacity,
        allow_guests: true,
        max_guests: 1,
      },
    });
    await ok(created, 'create the event');
    return ((await created.json()) as AdminEvent).id;
  });
}

/** A typed-name sign-up as a member (the viewer session), through the API. */
async function signUpTyped(
  baseURL: string | undefined,
  eventId: number,
  name: string,
  email: string,
  guests: number,
): Promise<number> {
  return withApi(baseURL, VIEWER_STATE, async (api) => {
    const response = await api.post(`/api/club-events/${eventId}/registrations`, {
      data: { shooter_id: null, name, email, guests },
    });
    await ok(response, `sign up ${name}`);
    return ((await response.json()) as { registration_id: number }).registration_id;
  });
}

/** One roster entry, whichever way the page lays it out (a table row or a stacked row). */
function rosterEntry(page: Page, name: string, width: number): Locator {
  return width >= 1024
    ? page.getByRole('row').filter({ hasText: name })
    : page.getByRole('list', { name: 'Sign-ups' }).getByRole('listitem').filter({ hasText: name });
}

const WREN = 'Wren Ashby';
const ODELL = 'Odell Prewitt';
const TAMSIN = 'Tamsin Rowe';

for (const viewport of VIEWPORTS) {
  test(`the organizer runs a club event at ${viewport.width}: edit, promote, link, reset, cancel, restore`, async ({
    page,
    browser,
    baseURL,
  }) => {
    test.setTimeout(180_000);
    // Capacity 2: Wren is in, Odell and one guest need two spots and wait, Tamsin waits behind.
    const id = await seedEvent(baseURL, 2);
    await signUpTyped(baseURL, id, WREN, 'wren.ashby@example.com', 0);
    const odellId = await signUpTyped(baseURL, id, ODELL, 'odell.prewitt@example.com', 1);
    await signUpTyped(baseURL, id, TAMSIN, 'tamsin.rowe@example.com', 0);
    // Two wrong-email cancels on Odell's sign-up put a failure on it (so the reset shows).
    await withApi(baseURL, VIEWER_STATE, async (api) => {
      for (let i = 0; i < 2; i++) {
        const wrong = await api.post(`/api/club-events/${id}/registrations/${odellId}/cancel`, {
          data: { email: 'nobody@example.com' },
        });
        expect(wrong.status()).toBe(403);
      }
    });

    await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.setViewportSize(viewport);
    await page.goto('/admin/club-events');
    await page.getByRole('button', { name: new RegExp(TITLE) }).click();
    const entry = (name: string) => rosterEntry(page, name, viewport.width);
    await expect(entry(WREN)).toContainText('Going', SLOW);
    await expect(entry(ODELL)).toContainText('Waitlist #1');
    await expect(entry(TAMSIN)).toContainText('Waitlist #2');
    await expect(
      page.getByText('1 spot open; the next sign-up on the waitlist needs 2.'),
    ).toBeVisible();
    await expectNoSideScroll(page);

    // Copy emails: the going ones, comma-separated, onto the clipboard.
    await page.getByRole('button', { name: 'Copy emails' }).click();
    await expect(page.getByText('Copied 1 email')).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
      'wren.ashby@example.com',
    );

    // Reset cancel limit shows for the sign-up with failures, and goes once it is reset.
    await expect(
      page.getByRole('button', { name: `Reset cancel limit for ${TAMSIN}` }),
    ).toHaveCount(0);
    await page.getByRole('button', { name: `Reset cancel limit for ${ODELL}` }).click();
    await expect(page.getByRole('button', { name: `Reset cancel limit for ${ODELL}` })).toHaveCount(
      0,
      SLOW,
    );

    // Edit the capacity: three spots now fit Odell and the guest, and Tamsin moves up to #1.
    await page.getByLabel('Capacity', { exact: true }).fill('3');
    await page.getByRole('button', { name: 'Save changes' }).click();
    await expect(page.getByText('Saved')).toBeVisible(SLOW);
    await expect(entry(ODELL)).toContainText('Going', SLOW);
    await expect(entry(TAMSIN)).toContainText('Waitlist #1');

    // Edit the guests: Odell's guest stays home, so the spots go from three taken to two.
    await page.getByRole('button', { name: `Guests for ${ODELL}` }).click();
    const guests = page.getByRole('dialog', { name: `Guests for ${ODELL}` });
    await guests.getByLabel('Guests', { exact: true }).fill('0');
    await guests.getByRole('button', { name: 'Save' }).click();
    await expect(guests).toHaveCount(0, SLOW);
    // One spot opened by that change, so Tamsin (one spot) moves up on its own.
    await expect(entry(TAMSIN)).toContainText('Going', SLOW);

    // Remove Wren behind its confirm: the list now holds Odell and Tamsin only.
    await page.getByRole('button', { name: `Remove ${WREN}` }).click();
    const remove = page.getByRole('dialog', { name: 'Remove from the list' });
    await expect(remove).toContainText(`Remove ${WREN} from the list?`);
    await remove.getByRole('button', { name: 'Remove' }).click();
    await expect(remove).toHaveCount(0, SLOW);
    await expect(entry(WREN)).toContainText('Removed', SLOW);

    // Link Tamsin's typed name to the shooter list entry Hadley, Ike.
    await page.getByRole('button', { name: `Link ${TAMSIN}` }).click();
    const link = page.getByRole('dialog', { name: `Link ${TAMSIN} to a shooter` });
    await link.getByLabel('Shooter', { exact: true }).fill('Hadley');
    await link.getByRole('button', { name: /^Hadley, Ike/ }).click();
    await expect(
      link.getByText(/will be (deleted|moved)|already has an email on file/).first(),
    ).toBeVisible();
    await link.getByRole('button', { name: 'Link', exact: true }).click();
    await expect(page.getByRole('status').filter({ hasText: /^Linked\./ })).toBeVisible(SLOW);
    await expect(entry('Hadley, Ike')).toContainText('Going');
    await expect(page.getByRole('button', { name: `Link ${TAMSIN}` })).toHaveCount(0);
    await expectNoSideScroll(page);

    // Cancel the event behind its confirm; a member sees it cancelled, then restore.
    await page.getByRole('button', { name: 'Cancel event' }).click();
    const cancel = page.getByRole('dialog', { name: 'Cancel this club event' });
    await expect(cancel).toContainText('Everyone signed up will see it was cancelled.');
    await cancel.getByRole('button', { name: 'Cancel event' }).click();
    await expect(page.getByText('Club event cancelled')).toBeVisible(SLOW);
    await expect(page.getByRole('button', { name: 'Restore' })).toBeVisible();

    const viewer = await member(browser, baseURL, [], viewport);
    try {
      const memberPage = viewer.page;
      await memberPage.goto(`/club-events/${id}`);
      await expect(memberPage.getByText(CANCELLED)).toBeVisible(SLOW);
      await expect(memberPage.getByRole('button', { name: 'Sign up', exact: true })).toHaveCount(0);
      await expectNoSideScroll(memberPage);

      await page.getByRole('button', { name: 'Restore' }).click();
      const restore = page.getByRole('dialog', { name: 'Restore this club event' });
      await restore.getByRole('button', { name: 'Restore' }).click();
      await expect(page.getByText('Club event restored')).toBeVisible(SLOW);

      await memberPage.reload();
      await expect(memberPage.getByRole('button', { name: 'Sign up', exact: true })).toBeVisible(
        SLOW,
      );
      await expect(memberPage.getByText(CANCELLED)).toHaveCount(0);

      // The sign-up sheet with a 60-character typed name fits at this size too (Review Focus 5).
      await memberPage.getByRole('button', { name: 'Sign up', exact: true }).click();
      const sheet = memberPage.getByRole('dialog', { name: 'Sign up' });
      await sheet.getByRole('button', { name: "I'm not listed" }).click();
      await sheet.getByLabel('Your first and last name').fill(LONG_NAME);
      await sheet.getByLabel('Your email').fill('marigold@example.com');
      await expectNoSideScroll(memberPage);
      await sheet.getByRole('button', { name: 'Close' }).click();
      await expect(sheet).toHaveCount(0);
    } finally {
      await viewer.context.close();
    }
  });
}

test('turning the switch off mid-visit saves nothing and hides club events from members', async ({
  page,
  browser,
  baseURL,
}) => {
  test.setTimeout(120_000);
  const id = await seedEvent(baseURL, null);
  const bodies: Promise<string>[] = [];
  const m = await member(browser, baseURL, bodies);
  try {
    const sheet = await openSheet(m.page, id);
    await sheet.getByRole('button', { name: "I'm not listed" }).click();
    await sheet.getByLabel('Your first and last name').fill('Quincy Ames');
    await sheet.getByLabel('Your email').fill('quincy.ames@example.com');
    // The organizer turns the switch off while the sheet is open. The sign-up is refused with
    // "Nothing was saved" (§5.1, §5.9), and the API answers as for an unknown route.
    await withApi(baseURL, ADMIN_STATE, async (api) =>
      ok(await api.put('/api/admin/features/events', { data: { enabled: false } }), 'switch off'),
    );
    await sheet.getByRole('button', { name: 'Sign me up' }).click();
    // The sheet says so and stays up; closing it lets the page learn the switch is off.
    await expect(sheet.getByText(SWITCHED_OFF)).toBeVisible(SLOW);
    await expectNoSideScroll(m.page);
    await sheet.getByRole('button', { name: 'Close' }).click();
    await expect(m.page.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible(
      SLOW,
    );
    await expect(m.page.getByRole('dialog')).toHaveCount(0);
    await expectNoSideScroll(m.page);
    expect((await m.page.request.get(`/api/club-events/${id}`)).status()).toBe(404);
    await m.page.goto('/');
    await whenSettled(m.page);
    // Positive control: the milestone card shows only once the switches are known.
    await expect(m.page.getByRole('region', { name: /^Club milestone/ })).toBeVisible(SLOW);
    await expect(m.page.getByRole('region', { name: 'Coming up' })).toHaveCount(0);

    // The admin still reaches the event in preview, and nobody signed up.
    await page.setViewportSize(VIEWPORTS[1]);
    await page.goto(`/club-events/${id}`);
    await expect(page.getByRole('heading', { level: 1, name: TITLE })).toBeVisible(SLOW);
    await expect(page.getByText('Admin preview').first()).toBeVisible();
    await expect(page.getByText('Quincy Ames')).toHaveCount(0);
    await expect(page.getByText(EMPTY_ROSTER)).toBeVisible();
  } finally {
    await m.context.close();
  }
});
