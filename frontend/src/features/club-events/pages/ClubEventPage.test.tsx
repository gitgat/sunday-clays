import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { FeatureGate } from '../../../components/FeatureGate';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { ClubEventDetail } from '../api';
import { fallFunShoot, signedUp } from '../mocks';
import { allSignups, saveSignup } from '../tokens';
import { ClubEventPage } from './ClubEventPage';

function featuresOn() {
  server.use(http.get('*/api/features', () => HttpResponse.json({ switches: { events: true } })));
}

function serve(detail: Partial<ClubEventDetail>) {
  server.use(
    http.get('*/api/club-events/:id', () => HttpResponse.json({ ...fallFunShoot, ...detail })),
  );
}

function renderPage() {
  return renderWithProviders(<ClubEventPage />, {
    route: '/club-events/1',
    path: '/club-events/:id',
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ClubEventPage', () => {
  it('shows the title, club-time date, notes as plain text and the facts', async () => {
    featuresOn();
    serve({ notes: '<b>x</b>\nsecond line' });
    renderPage();
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Fall Fun Shoot' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Sat, Oct 17 · 11:30 PM')).toBeInTheDocument();
    const notes = screen.getByText(/<b>x<\/b>/);
    expect(notes).toHaveClass('whitespace-pre-line', 'break-words');
    expect(notes.querySelector('b')).toBeNull();
    expect(screen.getByText('Guests welcome, up to 2 each')).toBeInTheDocument();
    expect(screen.getByText('Sign up by Fri, Oct 16, 8:00 PM')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign up' })).toBeEnabled();
  });

  it('lists who is coming, then the numbered waitlist, with guests and links', async () => {
    featuresOn();
    renderPage();
    const going = await screen.findByRole('list', { name: 'Going' });
    // names never go into a shared image (§5.7.3): the roster sits inside data-share-exclude
    expect(going.closest('[data-share-exclude]')).not.toBeNull();
    expect(
      screen.getByRole('list', { name: 'Waitlist' }).closest('[data-share-exclude]'),
    ).not.toBeNull();
    expect(within(going).getByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/3',
    );
    expect(within(going).getByText('+1')).toBeInTheDocument();
    const waitlist = screen.getByRole('list', { name: 'Waitlist' });
    expect(within(waitlist).getByText('Pat Kim')).toBeInTheDocument();
    expect(within(waitlist).getByText('1.')).toBeInTheDocument();
    expect(screen.getByText('3 of 4 spots taken · 1 on the waitlist')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: "Cancel Dana Quill's spot" })).toBeInTheDocument();
  });

  it("marks this device's row and cancels it with its token", async () => {
    featuresOn();
    saveSignup(12, { eventId: 1, token: 'tok-12', status: 'going' });
    let body: unknown = null;
    server.use(
      http.post('*/api/club-events/1/registrations/12/cancel', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ status: 'cancelled', promoted: 0 });
      }),
    );
    const { user } = renderPage();
    expect(await screen.findByText("You're in. See you there!")).toBeInTheDocument();
    expect(screen.getByText('You')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sign up' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Cancel my spot' }));
    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel my spot' }),
    );
    await waitFor(() => expect(body).toEqual({ token: 'tok-12' }));
    await waitFor(() => expect(allSignups()).toEqual([]));
  });

  it('drops a stale token and cancels the new sign-up', async () => {
    featuresOn();
    saveSignup(5, { eventId: 1, token: 'removed', status: 'going' }); // not in the roster any more
    saveSignup(12, { eventId: 1, token: 'tok-12', status: 'going' });
    const posted: string[] = [];
    server.use(
      http.post('*/api/club-events/1/registrations/:rid/cancel', async ({ params, request }) => {
        posted.push(`${String(params.rid)} ${JSON.stringify(await request.json())}`);
        return HttpResponse.json({ status: 'cancelled', promoted: 0 });
      }),
    );
    const { user } = renderPage();
    await screen.findByText("You're in. See you there!");
    await waitFor(() => expect(allSignups().map((s) => s.registrationId)).toEqual([12]));
    await user.click(screen.getByRole('button', { name: 'Cancel my spot' }));
    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel my spot' }),
    );
    // Review Focus 4: the new registration is the one cancelled, never the stale id 5
    await waitFor(() => expect(posted).toEqual(['12 {"token":"tok-12"}']));
  });

  it("keeps this device's tokens on the switch's 404 and refetches the switches (§5.1, §5.9)", async () => {
    saveSignup(12, { eventId: 1, token: 'tok-12', status: 'going' });
    let switchReads = 0;
    server.use(
      http.get('*/api/features', () => {
        switchReads += 1;
        return HttpResponse.json({ switches: { events: true } });
      }),
      // the unknown-path body the gate answers while the switch is off (D1): code http_404
      http.get('*/api/club-events/:id', () =>
        HttpResponse.json({ detail: 'Not Found' }, { status: 404 }),
      ),
    );
    renderWithProviders(
      <FeatureGate feature="events">
        <ClubEventPage />
      </FeatureGate>,
      { route: '/club-events/1', path: '/club-events/:id' },
    );
    await waitFor(() => expect(switchReads).toBeGreaterThan(1));
    expect(allSignups().map((s) => s.registrationId)).toEqual([12]); // only club_event_not_found drops them
  });

  it('shows "Good news" once a waitlisted sign-up is going', async () => {
    featuresOn();
    saveSignup(12, { eventId: 1, token: 'tok-12', status: 'waitlist' });
    renderPage();
    expect(await screen.findByText("Good news: a spot opened and you're in.")).toBeInTheDocument();
  });

  it("keeps a cancelled event's roster visible below its banner, with Cancel buttons", async () => {
    featuresOn();
    serve({ state: 'cancelled' });
    renderPage();
    const banner = await screen.findByText('This event was cancelled by the organizers.');
    const roster = screen.getByRole('list', { name: 'Going' });
    expect(banner.compareDocumentPosition(roster) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByRole('button', { name: "Cancel Dana Quill's spot" })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sign up' })).not.toBeInTheDocument();
  });

  it('closes sign-ups and cancels once started; trusts state over the device clock', async () => {
    featuresOn();
    serve({ state: 'started', upcoming: false });
    renderPage();
    expect(await screen.findByRole('button', { name: 'Sign-ups closed' })).toBeDisabled();
    expect(
      screen.queryByRole('button', { name: "Cancel Dana Quill's spot" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Happening now')).not.toBeInTheDocument();
  });

  it('uses past tense and offers no action once the event is over (Ruling F3)', async () => {
    featuresOn();
    saveSignup(12, { eventId: 1, token: 'tok-12', status: 'going' });
    serve({ state: 'started', upcoming: false, spots_taken: 4, waitlist_count: 0 });
    renderPage();
    expect(await screen.findByText('You signed up.')).toBeInTheDocument();
    expect(screen.queryByText(/See you there/)).not.toBeInTheDocument();
    expect(screen.queryByText(/join the waitlist/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Sign up by/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancel my spot' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Cancel .*spot$/ })).not.toBeInTheDocument();
  });

  it('shows a past cancelled event as past, with no cancel action either', async () => {
    featuresOn();
    saveSignup(12, { eventId: 1, token: 'tok-12', status: 'going' });
    serve({ state: 'cancelled', upcoming: false });
    renderPage();
    expect(await screen.findByText('This event was cancelled by the organizers.')).toBeVisible();
    expect(screen.getByText('This club event was cancelled.')).toBeInTheDocument();
    expect(screen.queryByText(/kept in case/)).not.toBeInTheDocument();
    expect(screen.queryByText(/See you there/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancel my spot' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Cancel .*spot$/ })).not.toBeInTheDocument();
  });

  it("keeps this device's spot on a cancelled event, with Cancel, and no see-you-there", async () => {
    featuresOn();
    saveSignup(12, { eventId: 1, token: 'tok-12', status: 'going' });
    serve({ state: 'cancelled' });
    renderPage();
    expect(
      await screen.findByText('Your spot is kept in case the organizers restore this club event.'),
    ).toBeInTheDocument();
    expect(screen.queryByText(/See you there/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel my spot' })).toBeInTheDocument();
  });

  it('shows the empty and the purged roster lines', async () => {
    featuresOn();
    serve({ roster: [], spots_taken: 0, waitlist_count: 0, signups: 0 });
    const first = renderPage();
    expect(await screen.findByText('No one has signed up yet. Be the first.')).toBeInTheDocument();
    first.unmount();
    serve({ roster: [], purged: true, state: 'started' });
    renderPage();
    expect(
      await screen.findByText('The sign-up list was cleared 30 days after the event.'),
    ).toBeInTheDocument();
  });

  it("forgets this event's tokens when it was deleted", async () => {
    featuresOn();
    saveSignup(12, { eventId: 1, token: 'tok-12', status: 'going' });
    server.use(
      http.get('*/api/club-events/:id', () =>
        HttpResponse.json(
          { error: { code: 'club_event_not_found', message: 'That club event does not exist.' } },
          { status: 404 },
        ),
      ),
    );
    renderPage();
    expect(await screen.findByText("That club event isn't on the list.")).toBeInTheDocument();
    await waitFor(() => expect(allSignups()).toEqual([]));
  });

  it('works with storage blocked: no own row, the email path still opens', async () => {
    featuresOn();
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    const { user } = renderPage();
    await user.click(await screen.findByRole('button', { name: "Cancel Dana Quill's spot" }));
    expect(screen.getByLabelText('Type the email used for this sign-up.')).toBeInTheDocument();
  });

  async function signUpTyped(user: ReturnType<typeof renderPage>['user'], name: string) {
    const sheet = within(screen.getByRole('dialog'));
    await user.click(sheet.getByRole('button', { name: "I'm not listed" }));
    await user.type(screen.getByLabelText('Your first and last name'), name);
    await user.type(screen.getByLabelText('Your email'), 'who@example.com');
    await user.click(sheet.getByRole('button', { name: 'Sign me up' }));
  }

  it('lets this device sign up someone else, keeping both tokens', async () => {
    featuresOn();
    saveSignup(12, { eventId: 1, token: 'tok-12', status: 'going' });
    const { user } = renderPage();
    await screen.findByText("You're in. See you there!");
    expect(screen.queryByRole('button', { name: 'Sign up' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Sign up someone else' }));
    expect(
      within(screen.getByRole('dialog')).getByRole('searchbox', { name: "Who's signing up?" }),
    ).toBeInTheDocument();
    await signUpTyped(user, 'Cal Cy');
    await waitFor(() =>
      expect(
        allSignups()
          .map((s) => s.registrationId)
          .sort(),
      ).toEqual([12, 21]),
    );
  });

  it('offers no second sign-up once the event is not open', async () => {
    featuresOn();
    saveSignup(12, { eventId: 1, token: 'tok-12', status: 'going' });
    serve({ state: 'closed' });
    renderPage();
    await screen.findByText("You're in. See you there!");
    expect(screen.queryByRole('button', { name: 'Sign up someone else' })).not.toBeInTheDocument();
  });

  it('marks every row this device signed up as You', async () => {
    featuresOn();
    saveSignup(11, { eventId: 1, token: 'tok-11', status: 'going' });
    saveSignup(12, { eventId: 1, token: 'tok-12', status: 'going' });
    renderPage();
    await screen.findByText(/You're in/);
    expect(screen.getAllByText('You')).toHaveLength(2);
  });

  it('announces the sign-up and moves focus to the new status', async () => {
    featuresOn();
    server.use(
      http.post('*/api/club-events/:id/registrations', () =>
        HttpResponse.json({ ...signedUp, registration_id: 12, token: 'tok-12' }, { status: 201 }),
      ),
    );
    const { user } = renderPage();
    await user.click(await screen.findByRole('button', { name: 'Sign up' }));
    const live = screen.getByTestId('club-event-announcer');
    expect(live).toHaveAttribute('aria-live', 'polite');
    expect(live.textContent).toBe('');
    await signUpTyped(user, 'Dana Quill');
    await waitFor(() => expect(live).toHaveTextContent("You're in. See you there!"));
    await waitFor(() => expect(screen.getByRole('region', { name: 'Your sign-up' })).toHaveFocus());
  });

  it('announces a cancel and puts focus on the title', async () => {
    featuresOn();
    saveSignup(12, { eventId: 1, token: 'tok-12', status: 'going' });
    const { user } = renderPage();
    await user.click(await screen.findByRole('button', { name: 'Cancel my spot' }));
    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel my spot' }),
    );
    await waitFor(() =>
      expect(screen.getByTestId('club-event-announcer')).toHaveTextContent(
        'Your spot was cancelled.',
      ),
    );
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1, name: 'Fall Fun Shoot' })).toHaveFocus(),
    );
  });

  it('re-announces an identical message each time it happens', async () => {
    featuresOn();
    server.use(
      http.post('*/api/club-events/1/registrations/12/cancel', () =>
        HttpResponse.json({ status: 'cancelled', promoted: 0 }),
      ),
    );
    const { user } = renderPage();
    const cancelDana = async () => {
      await user.click(await screen.findByRole('button', { name: "Cancel Dana Quill's spot" }));
      await user.type(
        screen.getByLabelText('Type the email used for this sign-up.'),
        'dana@example.com',
      );
      await user.click(
        within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel spot' }),
      );
    };
    await cancelDana();
    const announcer = screen.getByTestId('club-event-announcer');
    await waitFor(() => expect(announcer).toHaveTextContent("Dana Quill's spot was cancelled."));
    const first = announcer.firstChild;
    await cancelDana();
    await waitFor(() => expect(announcer.firstChild).not.toBe(first)); // a fresh node is announced
    expect(announcer).toHaveTextContent("Dana Quill's spot was cancelled.");
  });

  it('names the other person when this device signs someone else up', async () => {
    featuresOn();
    saveSignup(11, { eventId: 1, token: 'tok-11', status: 'going' });
    server.use(
      http.post('*/api/club-events/:id/registrations', () =>
        HttpResponse.json({ ...signedUp, registration_id: 12, token: 'tok-12' }, { status: 201 }),
      ),
    );
    const { user } = renderPage();
    await user.click(await screen.findByRole('button', { name: 'Sign up someone else' }));
    const sheet = within(screen.getByRole('dialog'));
    expect(sheet.getByRole('searchbox', { name: "Who's signing up?" })).toBeInTheDocument();
    expect(sheet.queryByText('Who are you?')).not.toBeInTheDocument();
    await signUpTyped(user, 'Dana Quill');
    await waitFor(() =>
      expect(screen.getByTestId('club-event-announcer')).toHaveTextContent('Dana Quill is in.'),
    );
    expect(screen.getByTestId('club-event-announcer')).not.toHaveTextContent(/You're in/);
  });

  it('announces cancelling someone else by name', async () => {
    featuresOn();
    server.use(
      http.post('*/api/club-events/1/registrations/12/cancel', () =>
        HttpResponse.json({ status: 'cancelled', promoted: 0 }),
      ),
    );
    const { user } = renderPage();
    await user.click(await screen.findByRole('button', { name: "Cancel Dana Quill's spot" }));
    await user.type(
      screen.getByLabelText('Type the email used for this sign-up.'),
      'dana@example.com',
    );
    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel spot' }),
    );
    await waitFor(() =>
      expect(screen.getByTestId('club-event-announcer')).toHaveTextContent(
        "Dana Quill's spot was cancelled.",
      ),
    );
  });

  it("treats a sign-up made with storage blocked as this device's for the visit", async () => {
    featuresOn();
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    let body: unknown = null;
    server.use(
      http.post('*/api/club-events/:id/registrations', () =>
        HttpResponse.json({ ...signedUp, registration_id: 12, token: 'tok-12' }, { status: 201 }),
      ),
      http.post('*/api/club-events/1/registrations/12/cancel', async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ status: 'cancelled', promoted: 0 });
      }),
    );
    const { user } = renderPage();
    await user.click(await screen.findByRole('button', { name: 'Sign up' }));
    await signUpTyped(user, 'Dana Quill');
    expect(await screen.findByRole('region', { name: 'Your sign-up' })).toBeInTheDocument();
    expect(screen.getByText('You')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Cancel my spot' }));
    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel my spot' }),
    );
    await waitFor(() => expect(body).toEqual({ token: 'tok-12' }));
  });

  it('wraps long notes and names', async () => {
    featuresOn();
    const long = 'x'.repeat(120);
    serve({
      notes: `https://${long}`,
      roster: [
        {
          registration_id: 12,
          name: 'Q'.repeat(29) + ' ' + 'D'.repeat(30),
          shooter_id: null,
          guests: 0,
          status: 'going',
          waitlist_position: null,
        },
      ],
    });
    renderPage();
    expect(await screen.findByText(`https://${long}`)).toHaveClass('break-words');
    expect(screen.getByText('Q'.repeat(29) + ' ' + 'D'.repeat(30)).closest('li')).toHaveClass(
      'break-words',
    );
  });

  it('shows the after-race line when a typed email was not used', async () => {
    featuresOn();
    server.use(
      http.get('*/api/club-events/:id/signup-check', () =>
        HttpResponse.json({ has_email: false, already_signed_up: false }),
      ),
      http.post('*/api/club-events/:id/registrations', () =>
        HttpResponse.json(
          {
            registration_id: 12,
            token: 'tok-12',
            status: 'going',
            waitlist_position: null,
            email_used: 'on_file',
          },
          { status: 201 },
        ),
      ),
    );
    const { user } = renderPage();
    await user.click(await screen.findByRole('button', { name: 'Sign up' }));
    const sheet = within(screen.getByRole('dialog'));
    await user.type(sheet.getByRole('searchbox', { name: 'Who are you?' }), 'hadley');
    await user.click(await sheet.findByRole('button', { name: 'Hadley, Ike' }));
    await user.type(await sheet.findByLabelText('Your email'), 'ike.hadley@example.com');
    await user.click(sheet.getByRole('button', { name: 'Sign me up' }));
    expect(
      await screen.findByText(
        "We'll use the email already on file for Hadley, Ike. To cancel, use this device or ask an organizer.",
      ),
    ).toBeInTheDocument();
  });

  it('shows the admin preview badge while the switch is off', async () => {
    server.use(
      http.get('*/api/features', () => HttpResponse.json({ switches: { events: false } })),
    );
    renderWithProviders(<ClubEventPage />, {
      route: '/club-events/1',
      path: '/club-events/:id',
      role: 'admin',
    });
    expect(await screen.findByText('Admin preview')).toBeInTheDocument();
  });

  it('starts the sign-up sheet fresh each time it is opened', async () => {
    featuresOn();
    const { user } = renderPage();
    await user.click(await screen.findByRole('button', { name: 'Sign up' }));
    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: "I'm not listed" }),
    );
    await user.type(screen.getByLabelText('Your first and last name'), 'Dana Quill');
    await user.click(screen.getByRole('button', { name: 'Close' }));
    await user.click(screen.getByRole('button', { name: 'Sign up' }));
    expect(screen.getByRole('searchbox', { name: 'Who are you?' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Your first and last name')).not.toBeInTheDocument();
  });

  it('wraps an unbroken long linked name', async () => {
    featuresOn();
    serve({
      roster: [
        {
          registration_id: 12,
          name: 'Q'.repeat(60),
          shooter_id: 3,
          guests: 0,
          status: 'going',
          waitlist_position: null,
        },
      ],
    });
    renderPage();
    expect(await screen.findByRole('link', { name: 'Q'.repeat(60) })).toHaveClass(
      'min-w-0',
      'break-words',
    );
  });
});
