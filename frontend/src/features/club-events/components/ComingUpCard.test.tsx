import { screen, waitFor, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { WidgetSlot } from '../../home/components/WidgetSlot';
import { homeWidgets } from '../../home/widgets';
import { fallFunShoot, fallFunSummary } from '../mocks';
import { allSignups, saveSignup } from '../tokens';
import { ComingUpCard } from './ComingUpCard';

function switches(value: Record<string, boolean>) {
  server.use(http.get('*/api/features', () => HttpResponse.json({ switches: value })));
}

describe('ComingUpCard (§5.7.4)', () => {
  it('sends nothing and renders nothing for a viewer while the switch is off', async () => {
    switches({});
    let asked = 0;
    server.use(
      http.get('*/api/club-events', () => {
        asked += 1;
        return HttpResponse.json({ upcoming: [fallFunSummary], past: [] });
      }),
    );
    const { container } = renderWithProviders(<ComingUpCard />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
    expect(asked).toBe(0);
  });

  it('shows the next club event with its facts and a Sign up link', async () => {
    switches({ events: true });
    renderWithProviders(<ComingUpCard />);
    const card = await screen.findByRole('region', { name: 'Coming up' });
    expect(within(card).getByText('Fall Fun Shoot')).toBeInTheDocument();
    expect(within(card).getByText('Sat, Oct 17 · 11:30 PM')).toBeInTheDocument();
    expect(within(card).getByText('3 of 4 spots taken')).toBeInTheDocument();
    expect(within(card).getByText('Sign up by Fri, Oct 16, 8:00 PM')).toBeInTheDocument();
    expect(within(card).getByRole('link', { name: 'Sign up' })).toHaveAttribute(
      'href',
      '/club-events/1',
    );
  });

  it('follows state, not the device clock: an old deadline with state open still says Sign up', async () => {
    switches({ events: true });
    server.use(
      http.get('*/api/club-events', () =>
        HttpResponse.json({
          upcoming: [{ ...fallFunSummary, signup_deadline: '2020-01-01T00:00:00Z' }],
          past: [],
        }),
      ),
    );
    renderWithProviders(<ComingUpCard />);
    expect(await screen.findByRole('link', { name: 'Sign up' })).toBeInTheDocument();
  });

  it('says "See details" and shows this device\'s chip once signed up', async () => {
    switches({ events: true });
    saveSignup(12, { eventId: 1, token: 'tok-12', status: 'going' });
    renderWithProviders(<ComingUpCard />);
    expect(await screen.findByRole('link', { name: 'See details' })).toBeInTheDocument();
    expect(await screen.findByText("You're in")).toBeInTheDocument();
  });

  it('shows "Waitlist #2" for a waitlist token with a roster row at position 2', async () => {
    switches({ events: true });
    saveSignup(14, { eventId: 1, token: 'tok-14', status: 'waitlist' });
    server.use(
      http.get('*/api/club-events/:id', () =>
        HttpResponse.json({
          ...fallFunShoot,
          roster: [
            ...fallFunShoot.roster,
            {
              registration_id: 14,
              name: 'Amy Ace',
              shooter_id: null,
              guests: 0,
              status: 'waitlist',
              waitlist_position: 2,
            },
          ],
        }),
      ),
    );
    renderWithProviders(<ComingUpCard />);
    expect(await screen.findByText('Waitlist #2')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See details' })).toBeInTheDocument();
  });

  it('first says that an event this device signed up for was cancelled', async () => {
    switches({ events: true });
    saveSignup(12, { eventId: 9, token: 'tok', status: 'going' });
    let detailCalls = 0;
    server.use(
      http.get('*/api/club-events', () =>
        HttpResponse.json({
          upcoming: [
            { ...fallFunSummary, id: 9, state: 'cancelled' },
            { ...fallFunSummary, id: 1 },
          ],
          past: [],
        }),
      ),
      http.get('*/api/club-events/:id', ({ params }) => {
        detailCalls += 1;
        return HttpResponse.json({ ...fallFunShoot, id: Number(params.id) });
      }),
    );
    renderWithProviders(<ComingUpCard />);
    expect(
      await screen.findByText('Fall Fun Shoot on Sat, Oct 17 was cancelled.'),
    ).toBeInTheDocument();
    expect(detailCalls).toBe(1); // only the cancelled event's roster, to confirm this device is on it
  });

  it('asks Sign up, with no chip, when the token is stale (the roster no longer lists it)', async () => {
    switches({ events: true });
    saveSignup(99, { eventId: 1, token: 'removed', status: 'going' });
    renderWithProviders(<ComingUpCard />);
    expect(await screen.findByRole('link', { name: 'Sign up' })).toBeInTheDocument();
    expect(screen.queryByText("You're in")).not.toBeInTheDocument();
  });

  it('prunes tokens for events missing from the list', async () => {
    switches({ events: true });
    saveSignup(50, { eventId: 404, token: 'gone', status: 'going' });
    renderWithProviders(<ComingUpCard />);
    await screen.findByRole('region', { name: 'Coming up' });
    await waitFor(() => expect(allSignups()).toEqual([]));
  });

  it('does not say cancelled for an event this device is no longer on', async () => {
    switches({ events: true });
    saveSignup(55, { eventId: 9, token: 'removed', status: 'going' }); // not on its roster
    server.use(
      http.get('*/api/club-events', () =>
        HttpResponse.json({
          upcoming: [
            { ...fallFunSummary, id: 9, state: 'cancelled' },
            { ...fallFunSummary, id: 1 },
          ],
          past: [],
        }),
      ),
    );
    renderWithProviders(<ComingUpCard />);
    await screen.findByRole('link', { name: 'Sign up' });
    await new Promise((r) => setTimeout(r, 100));
    expect(screen.queryByText(/was cancelled/)).not.toBeInTheDocument();
  });

  it('renders nothing when the only upcoming club event is cancelled, even one this device joined', async () => {
    switches({ events: true });
    saveSignup(12, { eventId: 9, token: 'tok', status: 'going' });
    let answered = false;
    server.use(
      http.get('*/api/club-events', () => {
        answered = true;
        return HttpResponse.json({
          upcoming: [{ ...fallFunSummary, id: 9, state: 'cancelled' }],
          past: [],
        });
      }),
    );
    const { container } = renderWithProviders(<ComingUpCard />);
    await waitFor(() => expect(answered).toBe(true));
    expect(container).toBeEmptyDOMElement(); // §5.7.4: the Club events page still says it was cancelled
  });

  it('renders nothing when nothing is coming up', async () => {
    switches({ events: true });
    let answered = false;
    server.use(
      http.get('*/api/club-events', () => {
        answered = true;
        return HttpResponse.json({ upcoming: [], past: [] });
      }),
    );
    const { container } = renderWithProviders(<ComingUpCard />);
    await waitFor(() => expect(answered).toBe(true));
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the admin preview badge while the switch is off', async () => {
    switches({ events: false });
    renderWithProviders(<ComingUpCard />, { role: 'admin' });
    const card = await screen.findByRole('region', { name: 'Coming up' });
    expect(within(card).getByText('Admin preview')).toBeInTheDocument();
  });

  it('test_home_widget_after_next_sunday: appears below Next Sunday, never above it', async () => {
    switches({ events: true });
    let release: () => void = () => undefined;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get('*/api/club-events', async () => {
        await held;
        await delay(0);
        return HttpResponse.json({ upcoming: [fallFunSummary], past: [] });
      }),
    );
    const main = homeWidgets.filter((w) => w.id === 'next-sunday' || w.id === 'club-events-next');
    renderWithProviders(<WidgetSlot slot="main" widgets={main} meId={null} />);
    const nextSunday = await screen.findByRole('heading', { name: 'Next Sunday' });
    expect(screen.queryByRole('heading', { name: 'Coming up' })).not.toBeInTheDocument();
    release();
    const comingUp = await screen.findByRole('heading', { name: 'Coming up' });
    expect(
      nextSunday.compareDocumentPosition(comingUp) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});
