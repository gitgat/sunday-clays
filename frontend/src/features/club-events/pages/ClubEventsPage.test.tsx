import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { FeatureGate } from '../../../components/FeatureGate';
import { banquetPast, clubEventList, fallFunShoot, fallFunSummary } from '../mocks';
import { allSignups, PAST_OPEN_KEY, saveSignup } from '../tokens';
import { ClubEventsPage } from './ClubEventsPage';

function featuresOn() {
  server.use(http.get('*/api/features', () => HttpResponse.json({ switches: { events: true } })));
}

describe('ClubEventsPage', () => {
  it('lists upcoming cards and keeps past events collapsed', async () => {
    featuresOn();
    const { user } = renderWithProviders(<ClubEventsPage />, { route: '/club-events' });
    expect(screen.getByRole('heading', { level: 1, name: 'Club events' })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Club get-togethers beyond Sunday shoots. Sign up so organizers know who's coming.",
      ),
    ).toBeInTheDocument();
    const card = await screen.findByRole('link', { name: /Fall Fun Shoot/ });
    expect(card).toHaveAttribute('href', '/club-events/1');
    expect(within(card).getByText('Sat, Oct 17 · 11:30 PM')).toBeInTheDocument();
    expect(within(card).getByText('3 of 4 spots taken')).toBeInTheDocument();
    expect(within(card).getByText('Sign up by Fri, Oct 16, 8:00 PM')).toBeInTheDocument();
    const toggle = screen.getByRole('button', { name: 'Past events (1)' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('Summer Banquet')).not.toBeInTheDocument();
    await user.click(toggle);
    expect(screen.getByText('Summer Banquet')).toBeInTheDocument();
    expect(screen.getByText('Sat, Aug 1 · 28 came')).toBeInTheDocument();
    expect(localStorage.getItem(PAST_OPEN_KEY)).toBe('1');
  });

  it('says Cancelled, not "N came", for a past cancelled event', async () => {
    featuresOn();
    server.use(
      http.get('*/api/club-events', () =>
        HttpResponse.json({
          upcoming: [],
          past: [{ ...banquetPast, state: 'cancelled', signups: 5 }],
        }),
      ),
    );
    const { user } = renderWithProviders(<ClubEventsPage />, { route: '/club-events' });
    await user.click(await screen.findByRole('button', { name: 'Past events (1)' }));
    expect(screen.getByText('Sat, Aug 1 · Cancelled')).toBeInTheDocument();
    expect(screen.queryByText(/came/)).not.toBeInTheDocument();
  });

  it("marks a cancelled event and keeps this device's chip off it", async () => {
    featuresOn();
    let detailReads = 0;
    saveSignup(13, { eventId: 1, token: 'tok-13', status: 'waitlist' });
    server.use(
      http.get('*/api/club-events', () =>
        HttpResponse.json({ upcoming: [{ ...fallFunSummary, state: 'cancelled' }], past: [] }),
      ),
      http.get('*/api/club-events/:id', () => {
        detailReads += 1;
        return HttpResponse.json(fallFunShoot);
      }),
    );
    renderWithProviders(<ClubEventsPage />, { route: '/club-events' });
    expect(await screen.findByText('Cancelled')).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 100)); // time for any chip fetch to settle
    expect(detailReads).toBe(0);
    expect(screen.queryByText('Waitlist #1')).not.toBeInTheDocument();
  });

  it('drops stored sign-ups for events that are gone or purged', async () => {
    featuresOn();
    saveSignup(11, { eventId: 1, token: 'keep', status: 'going' });
    saveSignup(12, { eventId: 2, token: 'purged', status: 'going' }); // banquetPast is purged
    saveSignup(13, { eventId: 77, token: 'gone', status: 'going' });
    renderWithProviders(<ClubEventsPage />, { route: '/club-events' });
    await screen.findByRole('link', { name: /Fall Fun Shoot/ });
    await waitFor(() => expect(allSignups().map((s) => s.registrationId)).toEqual([11]));
  });

  it('says when nothing is coming up', async () => {
    featuresOn();
    server.use(http.get('*/api/club-events', () => HttpResponse.json({ upcoming: [], past: [] })));
    renderWithProviders(<ClubEventsPage />, { route: '/club-events' });
    expect(
      await screen.findByText('No club events coming up. Check back soon.'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Past events/ })).not.toBeInTheDocument();
  });
});

describe('ClubEventsPage errors', () => {
  it('offers Try again when the list fails to load, and loads on retry', async () => {
    featuresOn();
    let failing = true;
    server.use(
      http.get('*/api/club-events', () =>
        failing ? HttpResponse.json({}, { status: 500 }) : HttpResponse.json(clubEventList),
      ),
    );
    const { user } = renderWithProviders(<ClubEventsPage />, { route: '/club-events' });
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not load club events. Try again.',
    );
    failing = false;
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('link', { name: /Fall Fun Shoot/ })).toBeInTheDocument();
  });

  it("says the list is unavailable on the gate's 404", async () => {
    featuresOn();
    server.use(
      http.get('*/api/club-events', () =>
        HttpResponse.json({ detail: 'Not Found' }, { status: 404 }),
      ),
    );
    renderWithProviders(<ClubEventsPage />, { route: '/club-events' });
    expect(await screen.findByText("Club events aren't available right now.")).toBeInTheDocument();
  });

  it('closes the past events again and remembers it', async () => {
    featuresOn();
    const { user } = renderWithProviders(<ClubEventsPage />, { route: '/club-events' });
    const toggle = await screen.findByRole('button', { name: 'Past events (1)' });
    await user.click(toggle);
    await user.click(toggle);
    expect(localStorage.getItem(PAST_OPEN_KEY)).toBe('0');
  });

  it('refetches the switches when the gate answers 404', async () => {
    let reads = 0;
    server.use(
      http.get('*/api/features', () => {
        reads += 1;
        return HttpResponse.json({ switches: { events: true } });
      }),
      http.get('*/api/club-events', () =>
        HttpResponse.json({ detail: 'Not Found' }, { status: 404 }),
      ),
    );
    renderWithProviders(
      <FeatureGate feature="events">
        <ClubEventsPage />
      </FeatureGate>,
      { route: '/club-events' },
    );
    await waitFor(() => expect(reads).toBeGreaterThan(1));
  });

  it('wraps an unbroken long past-event title', async () => {
    featuresOn();
    server.use(
      http.get('*/api/club-events', () =>
        HttpResponse.json({ upcoming: [], past: [{ ...banquetPast, title: 'B'.repeat(60) }] }),
      ),
    );
    const { user } = renderWithProviders(<ClubEventsPage />, { route: '/club-events' });
    await user.click(await screen.findByRole('button', { name: 'Past events (1)' }));
    expect(screen.getByRole('link', { name: 'B'.repeat(60) })).toHaveClass(
      'min-w-0',
      'break-words',
    );
  });
});
