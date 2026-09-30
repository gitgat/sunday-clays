import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { delay, http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { clearMe, getMe, setMe } from '../../../lib/me';
import { expectExplainer } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { ShooterRound } from '../api';
import { latestEvent, meDetail, meRounds } from '../mocks';
import type { HomeWidget } from '../widgets';
import { lastResult, MePanel } from './MePanel';

const nextTrophy: HomeWidget = {
  id: 'next-trophy',
  order: 10,
  slot: 'me',
  Component: ({ meId }) => <p>next trophy for {meId}</p>,
};
const mainWidget: HomeWidget = {
  id: 'main-only',
  order: 5,
  slot: 'main',
  Component: () => <p>main widget</p>,
};
const latest = meRounds[0] as ShooterRound;

describe('lastResult', () => {
  it('uses the best round of the latest attended date', () => {
    expect(lastResult([...meRounds].reverse())).toEqual({
      date: '2026-09-27',
      score: 37,
      rank: 16,
      ratingMove: 0.1,
    });
  });

  it('falls back to the top score when no round is marked best yet', () => {
    const r = (id: number, score: number): ShooterRound => ({
      ...latest,
      round_id: id,
      score,
      is_best_round: false,
      event_rank: null,
      mu_before: null,
      mu_after: null,
    });
    expect(lastResult([r(1, 35), r(2, 30), r(3, 40)])).toEqual({
      date: '2026-09-27',
      score: 40,
      rank: null,
      ratingMove: null,
    });
  });

  it('is null without rounds', () => {
    expect(lastResult([])).toBeNull();
  });
});

describe('MePanel', () => {
  beforeEach(() => {
    clearMe();
  });

  it('invites you to pick yourself when no me id is set', () => {
    renderWithProviders(<MePanel meId={null} onCleared={vi.fn()} widgets={[nextTrophy]} />);
    expect(screen.getByText(/tap “That’s me”/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Go to Shooters' })).toHaveAttribute(
      'href',
      '/shooters',
    );
    expect(screen.queryByText(/next trophy/)).not.toBeInTheDocument();
  });

  it('shows your last result, rating move, odometer and me-slot widgets', async () => {
    server.use(
      http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
      http.get('*/api/shooters/:id/rounds', () => HttpResponse.json(meRounds)),
    );
    renderWithProviders(
      <MePanel meId={3} onCleared={vi.fn()} widgets={[nextTrophy, mainWidget]} />,
    );
    expect(await screen.findByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/3',
    );
    expect(await screen.findByText('37 · 16th')).toBeInTheDocument();
    expect(screen.getByText('+0.1')).toBeInTheDocument();
    expect(screen.getByText('9,427')).toBeInTheDocument();
    expect(screen.getByText('next trophy for 3')).toBeInTheDocument();
    expect(screen.queryByText('main widget')).not.toBeInTheDocument();
  });

  it('explains the last result and the totals, and calls the odometer count Sundays', async () => {
    server.use(
      http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
      http.get('*/api/shooters/:id/rounds', () => HttpResponse.json(meRounds)),
      http.get('*/api/events/:date', () => HttpResponse.json(latestEvent)),
    );
    renderWithProviders(<MePanel meId={3} onCleared={vi.fn()} widgets={[]} />);
    const panel = await screen.findByRole('region', { name: 'Your panel' });
    await screen.findByText('37 · 16th');
    await expectExplainer(panel, 'About your last Sunday', { read: true });
    await expectExplainer(panel, 'About your totals', { read: true });
    expect(screen.getByText('Sundays')).toBeInTheDocument();
    expect(screen.queryByText('Events')).not.toBeInTheDocument();
    // The odometer is lifetime, and its tag says so next to the disclosure.
    expect(within(panel).getByText('Lifetime')).toBeVisible();
  });

  it('shows a dash, not 0.0, for the rating move of a partial-results Sunday', async () => {
    server.use(
      http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
      http.get('*/api/shooters/:id/rounds', () =>
        HttpResponse.json([{ ...latest, field_median: null, mu_before: 35, mu_after: 35 }]),
      ),
    );
    renderWithProviders(<MePanel meId={3} onCleared={vi.fn()} widgets={[]} />);
    await screen.findByText('37 · 16th');
    // The dash comes from the rounds already loaded, with no second request to flash a 0.0 first.
    expect(screen.getByText('Rating move').closest('div')).toHaveTextContent('Rating move—');
  });

  it('shows the rating move of a full-results Sunday, even a real 0.0', async () => {
    server.use(
      http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
      http.get('*/api/shooters/:id/rounds', () =>
        HttpResponse.json([{ ...latest, mu_before: 35, mu_after: 35 }]),
      ),
      http.get('*/api/events/:date', () => HttpResponse.json(latestEvent)),
    );
    renderWithProviders(<MePanel meId={3} onCleared={vi.fn()} widgets={[]} />);
    await screen.findByText('37 · 16th');
    expect(screen.getByText('Rating move').closest('div')).toHaveTextContent('Rating move0.0');
  });

  it('keeps the global round-type filter on its links', async () => {
    server.use(
      http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
      http.get('*/api/shooters/:id/rounds', () => HttpResponse.json(meRounds)),
    );
    const { unmount } = renderWithProviders(<MePanel meId={3} onCleared={vi.fn()} widgets={[]} />, {
      route: '/?rt=sporting',
    });
    expect(await screen.findByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/3?rt=sporting',
    );
    expect(await screen.findByRole('link', { name: 'Sep 27, 2026' })).toHaveAttribute(
      'href',
      '/events/2026-09-27?rt=sporting',
    );
    unmount();
    renderWithProviders(<MePanel meId={null} onCleared={vi.fn()} widgets={[]} />, {
      route: '/?rt=sporting',
    });
    expect(screen.getByRole('link', { name: 'Go to Shooters' })).toHaveAttribute(
      'href',
      '/shooters?rt=sporting',
    );
  });

  it('shows the profile while the last result is still loading', async () => {
    server.use(
      http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
      http.get('*/api/shooters/:id/rounds', async () => {
        await delay('infinite');
        return HttpResponse.json(meRounds);
      }),
    );
    renderWithProviders(<MePanel meId={3} onCleared={vi.fn()} widgets={[]} />);
    expect(await screen.findByRole('link', { name: 'Hadley, Ike' })).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument();
    expect(screen.getByText('9,427')).toBeInTheDocument();
  });

  it('shows a dash for the finish when the round has no rank', async () => {
    server.use(
      http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
      http.get('*/api/shooters/:id/rounds', () =>
        HttpResponse.json([{ ...latest, event_rank: null }]),
      ),
    );
    renderWithProviders(<MePanel meId={3} onCleared={vi.fn()} widgets={[]} />);
    expect(await screen.findByText('37 · —')).toBeInTheDocument();
  });

  it('says no rounds yet for a shooter without rounds in the current filter', async () => {
    server.use(
      http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
      http.get('*/api/shooters/:id/rounds', () => HttpResponse.json([])),
    );
    renderWithProviders(<MePanel meId={3} onCleared={vi.fn()} widgets={[]} />);
    expect(await screen.findByText('No rounds yet.')).toBeInTheDocument();
  });

  it('says the last result is unavailable when rounds fail', async () => {
    server.use(
      http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
      http.get('*/api/shooters/:id/rounds', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<MePanel meId={3} onCleared={vi.fn()} widgets={[]} />);
    expect(await screen.findByText('Last result unavailable.')).toBeInTheDocument();
  });

  it('stale me id shows choose-again and clears it', async () => {
    setMe(999);
    const onCleared = vi.fn();
    const user = userEvent.setup();
    server.use(
      http.get('*/api/shooters/:id', () =>
        HttpResponse.json(
          { error: { code: 'shooter_not_found', message: 'No shooter with id 999' } },
          { status: 404 },
        ),
      ),
      http.get('*/api/shooters/:id/rounds', () => HttpResponse.json([])),
    );
    renderWithProviders(<MePanel meId={999} onCleared={onCleared} widgets={[]} />);
    expect(await screen.findByText(/couldn’t find your shooter profile/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Choose again' }));
    expect(getMe()).toBeNull();
    expect(onCleared).toHaveBeenCalledTimes(1);
  });

  it('shows a load failure for other errors', async () => {
    server.use(
      http.get('*/api/shooters/:id', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
      http.get('*/api/shooters/:id/rounds', () => HttpResponse.json([])),
    );
    renderWithProviders(<MePanel meId={3} onCleared={vi.fn()} widgets={[]} />);
    expect(await screen.findByText("Couldn't load your panel")).toBeInTheDocument();
  });
});
