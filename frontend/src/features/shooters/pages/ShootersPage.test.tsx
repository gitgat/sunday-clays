import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { clearMe, setMe } from '../../../lib/me';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { shooterList } from '../mocks';
import { ShootersPage } from './ShootersPage';

const requests: URLSearchParams[] = [];

describe('ShootersPage', () => {
  beforeEach(() => {
    clearMe();
    requests.length = 0;
    server.use(
      http.get('*/api/shooters', ({ request }) => {
        const params = new URL(request.url).searchParams;
        requests.push(params);
        const q = (params.get('q') ?? '').toLowerCase();
        return HttpResponse.json(
          shooterList.filter((s) => s.display_name.toLowerCase().includes(q)),
        );
      }),
    );
  });

  it('explains what Active only means', () => {
    renderWithProviders(<ShootersPage />, { route: '/shooters' });
    expect(screen.getByText('Active = shot in the last 12 months and has 5+ rounds')).toBeVisible();
  });

  it('lists every shooter with a memorial marker for the deceased and a guest tag', async () => {
    renderWithProviders(<ShootersPage />, { route: '/shooters' });
    const list = await screen.findByRole('list', { name: 'Shooters' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(4);
    const gilchrist = within(list).getByRole('link', { name: /Gilchrist, Melvin/ });
    expect(gilchrist).toHaveAttribute('href', '/shooters/41');
    expect(within(gilchrist).getByRole('img', { name: 'In memoriam' })).toBeInTheDocument();
    expect(
      within(within(list).getByRole('link', { name: /Mortlock, Beatrice/ })).getByText('Guest'),
    ).toBeInTheDocument();
    expect(requests[0]?.has('active')).toBe(false);
  });

  it('says "1 Sunday" for a single-Sunday shooter and pluralizes the rest', async () => {
    server.use(
      http.get('*/api/shooters', () =>
        HttpResponse.json(
          shooterList
            .filter((s) => s.shooter_id === 3 || s.shooter_id === 88)
            .map((s) => (s.shooter_id === 88 ? { ...s, n_rounds: 1, n_events: 1 } : s)),
        ),
      ),
    );
    renderWithProviders(<ShootersPage />, { route: '/shooters' });
    expect(await screen.findByRole('link', { name: /Mortlock, Beatrice/ })).toHaveTextContent(
      /1 Sunday · last Sep 6, 2026$/,
    );
    expect(screen.getByRole('link', { name: /Hadley, Ike/ })).toHaveTextContent(
      /267 Sundays · last Sep 27, 2026$/,
    );
  });

  it('keeps the global round-type filter on profile links', async () => {
    renderWithProviders(<ShootersPage />, { route: '/shooters?rt=super_sporting' });
    const list = await screen.findByRole('list', { name: 'Shooters' });
    expect(within(list).getByRole('link', { name: /Gilchrist, Melvin/ })).toHaveAttribute(
      'href',
      '/shooters/41?rt=super_sporting',
    );
  });

  it('searches by name as you type', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ShootersPage />, { route: '/shooters' });
    await user.type(await screen.findByRole('searchbox', { name: 'Search shooters' }), 'gilchrist');
    await waitFor(() => expect(requests.at(-1)?.get('q')).toBe('gilchrist'));
    // The previous rows stay on screen while each keystroke's query loads, so wait for the 'gilchrist' result itself.
    await waitFor(() =>
      expect(
        within(screen.getByRole('list', { name: 'Shooters' })).getAllByRole('listitem'),
      ).toHaveLength(1),
    );
    expect(
      within(screen.getByRole('list', { name: 'Shooters' })).getByRole('link', {
        name: /Gilchrist, Melvin/,
      }),
    ).toBeInTheDocument();
  });

  it('keeps the previous results on screen, marked busy, while a new search loads', async () => {
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get('*/api/shooters', async ({ request }) => {
        const params = new URL(request.url).searchParams;
        requests.push(params);
        const q = (params.get('q') ?? '').toLowerCase();
        if (q) await gate;
        return HttpResponse.json(
          shooterList.filter((s) => s.display_name.toLowerCase().includes(q)),
        );
      }),
    );
    try {
      const user = userEvent.setup();
      renderWithProviders(<ShootersPage />, { route: '/shooters' });
      expect(
        within(await screen.findByRole('list', { name: 'Shooters' })).getAllByRole('listitem'),
      ).toHaveLength(4);
      await user.type(screen.getByRole('searchbox', { name: 'Search shooters' }), 'hadley');
      await waitFor(() => expect(requests.at(-1)?.get('q')).toBe('hadley'));
      // No skeleton flash: the four previous rows stay, and the results area says it is updating.
      expect(screen.queryByRole('status', { name: 'Loading' })).not.toBeInTheDocument();
      const stale = screen.getByRole('list', { name: 'Shooters' });
      expect(within(stale).getAllByRole('listitem')).toHaveLength(4);
      expect(stale.closest('[aria-busy]')).toHaveAttribute('aria-busy', 'true');
      release();
      await waitFor(() =>
        expect(
          within(screen.getByRole('list', { name: 'Shooters' })).getAllByRole('listitem'),
        ).toHaveLength(1),
      );
      expect(screen.getByRole('list', { name: 'Shooters' }).closest('[aria-busy]')).toBeNull();
    } finally {
      release();
    }
  });

  it('keeps naming the search a no-match result belongs to while the next search loads', async () => {
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get('*/api/shooters', async ({ request }) => {
        const q = (new URL(request.url).searchParams.get('q') ?? '').toLowerCase();
        if (q !== 'zzz') await gate;
        return HttpResponse.json(
          shooterList.filter((s) => s.display_name.toLowerCase().includes(q)),
        );
      }),
    );
    try {
      const user = userEvent.setup();
      renderWithProviders(<ShootersPage />, { route: '/shooters?q=zzz' });
      expect(await screen.findByText('No shooters match “zzz”')).toBeInTheDocument();
      // Clearing the box starts the unfiltered load; until it lands the stale empty state still names "zzz"
      // (never a false "No shooters yet").
      await user.clear(screen.getByRole('searchbox', { name: 'Search shooters' }));
      await waitFor(() => expect(screen.getByRole('searchbox')).toHaveValue(''));
      expect(screen.getByText('No shooters match “zzz”')).toBeInTheDocument();
      expect(screen.queryByText('No shooters yet')).not.toBeInTheDocument();
      release();
      expect(await screen.findByRole('list', { name: 'Shooters' })).toBeInTheDocument();
    } finally {
      release();
    }
  });

  it('asks the server for active shooters only when the toggle is on', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ShootersPage />, { route: '/shooters' });
    await user.click(await screen.findByRole('switch', { name: 'Active only' }));
    await waitFor(() => expect(requests.at(-1)?.get('active')).toBe('true'));
  });

  it('marks the remembered shooter as you', async () => {
    setMe(3);
    renderWithProviders(<ShootersPage />, { route: '/shooters' });
    const hadley = await screen.findByRole('link', { name: /Hadley, Ike/ });
    expect(within(hadley).getByText('You')).toBeInTheDocument();
  });

  it('says when nothing matches the search', async () => {
    renderWithProviders(<ShootersPage />, { route: '/shooters?q=zzz' });
    expect(await screen.findByText('No shooters match “zzz”')).toBeInTheDocument();
  });

  it('says when there are no shooters at all', async () => {
    server.use(http.get('*/api/shooters', () => HttpResponse.json([])));
    renderWithProviders(<ShootersPage />, { route: '/shooters' });
    expect(await screen.findByText('No shooters yet')).toBeInTheDocument();
  });

  it('shows a load failure', async () => {
    server.use(
      http.get('*/api/shooters', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<ShootersPage />, { route: '/shooters' });
    expect(await screen.findByText("Couldn't load shooters")).toBeInTheDocument();
  });
});
