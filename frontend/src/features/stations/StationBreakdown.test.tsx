import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  captureCsv,
  expectChartControls,
  expectExplainer,
  openFullscreen,
} from '../../test/charts';
import { server } from '../../test/msw/server';
import { shooterStationsFixture } from './mocks';
import { profileSection } from './profileSection';
import { StationBreakdown } from './StationBreakdown';

function renderBreakdown(url = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <StationBreakdown shooterId={12} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

const none = {
  n_rounds: 0,
  n_sundays: 0,
  first_date: null,
  last_date: null,
  latest_date: null,
};

describe('StationBreakdown', () => {
  it('lists a lettered station by its label, after its number', async () => {
    const [four, nine] = shooterStationsFixture.stations;
    if (four === undefined) throw new Error('the shooter fixture has no stations');
    const sevenA = { ...four, label: '7A', station_no: 7 };
    server.use(
      http.get('*/api/shooters/:id/stations', () =>
        HttpResponse.json({ ...shooterStationsFixture, stations: [four, sevenA, nine] }),
      ),
    );
    renderBreakdown();
    const row = await screen.findByRole('row', { name: /^Station 7A\b/ });
    expect(row).toHaveTextContent('+4.80 pts');
    expect(screen.getAllByRole('rowheader').map((h) => h.textContent)).toEqual([
      'Station 4',
      'Station 7A',
      'Station 9',
    ]);
  });

  it('fullscreen and the CSV list every station, with no versus-field number under two rounds', async () => {
    const csv = captureCsv();
    const user = userEvent.setup();
    renderBreakdown('/?stdelta=table');
    const card = await screen.findByRole('region', { name: 'Where you lose targets' });
    // Inline: station 9 has one round, so it is not charted or listed.
    expect(within(card).getAllByRole('row')).toHaveLength(1 + 1);
    const dialog = await openFullscreen(user, card, 'Where you lose targets');
    expect(
      within(dialog).getByText(
        'Every station. Versus field is blank until a station has been shot twice.',
      ),
    ).toBeInTheDocument();
    const rows = within(dialog).getAllByRole('row');
    expect(rows).toHaveLength(1 + 2);
    expect(rows[2]).toHaveTextContent('9');
    expect(rows[2]).toHaveTextContent('42.86');
    expect(rows[2]).not.toHaveTextContent('-2.5');
    await user.click(within(card).getByRole('button', { name: 'CSV' }));
    await waitFor(() => expect(csv.names).toEqual(['shooter-12-stations.csv']));
    expect((await csv.text()).trimEnd().split('\r\n')).toEqual([
      'Station,Hit %,Field hit %,Versus field (pts),Rounds',
      '4,85.71,71.04,4.8,2',
      '9,42.86,50.19,,1',
    ]);
  });

  it('shows deltas only for stations shot at least twice', async () => {
    renderBreakdown();
    expect(await screen.findByRole('row', { name: /^Station 4\b/ })).toHaveTextContent('+4.80 pts');
    const nine = screen.getByRole('row', { name: /^Station 9\b/ });
    expect(nine).toHaveTextContent('—');
    expect(nine).not.toHaveTextContent('pts');
  });

  it('exposes Table and CSV controls on every chart', async () => {
    renderBreakdown();
    await screen.findByRole('region', { name: 'Station breakdown for this shooter' });
    expectChartControls(screen.getByRole('region', { name: 'Where you lose targets' }));
    expect(screen.getAllByRole('button', { name: 'Table' })).toHaveLength(1);
    expect([
      ...screen.queryAllByRole('button', { name: /csv/i }),
      ...screen.queryAllByRole('link', { name: /csv/i }),
    ]).toHaveLength(1);
  });

  it('explains the chart and the table in plain words', async () => {
    renderBreakdown();
    await screen.findByRole('region', { name: 'Where you lose targets' });
    await expectExplainer(
      screen.getByRole('region', { name: 'Where you lose targets' }),
      undefined,
      {
        read: true,
      },
    );
    await expectExplainer(
      screen.getByRole('region', { name: 'Station breakdown for this shooter' }),
      'About this table',
    );
  });

  it('asks for the era the switch names, current by default', async () => {
    const eras: (string | null)[] = [];
    server.use(
      http.get('*/api/shooters/:id/stations', ({ request }) => {
        eras.push(new URL(request.url).searchParams.get('era'));
        return HttpResponse.json(shooterStationsFixture);
      }),
    );
    const user = userEvent.setup();
    renderBreakdown();
    await screen.findByRole('row', { name: /^Station 4\b/ });
    expect(eras).toEqual(['current']);
    await user.click(screen.getByRole('button', { name: 'All setups' }));
    await waitFor(() => {
      expect(eras).toContain('all');
    });
    expect(screen.getByRole('button', { name: 'All setups' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('explains when no station has two rounds yet', async () => {
    server.use(
      http.get('*/api/shooters/:id/stations', () =>
        HttpResponse.json({
          ...shooterStationsFixture,
          stations: shooterStationsFixture.stations.filter((s) => s.n_rounds < 2),
        }),
      ),
    );
    renderBreakdown();
    expect(
      await screen.findByText(
        'Deltas appear once a station has been shot at least twice in the last 8 weeks.',
      ),
    ).toBeInTheDocument();
    expect(screen.queryAllByRole('button', { name: 'Table' })).toHaveLength(0);
  });

  it('says so when the shooter has no station sheets', async () => {
    server.use(
      http.get('*/api/shooters/:id/stations', () =>
        HttpResponse.json({ ...shooterStationsFixture, stations: [], coverage: none }),
      ),
    );
    renderBreakdown();
    expect(await screen.findByText('No station sheets for this shooter yet.')).toBeInTheDocument();
  });

  it('sends the window and shows the shooter their own scope line', async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get('*/api/shooters/:id/stations', ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return HttpResponse.json(shooterStationsFixture);
      }),
    );
    renderBreakdown();
    await screen.findByRole('row', { name: /^Station 4\b/ });
    expect(seen[0]?.get('since')).toBe('2026-08-03');
    expect(seen[0]?.get('as_of')).toBe('2026-09-27');
    expect(screen.getByRole('note', { name: 'Setups and dates shown' })).toHaveTextContent(
      'Current setups · Last 8 weeks · Aug 3 – Sep 27',
    );
  });

  it('says no sheets fall in the window, names their latest, and offers 12M and All', async () => {
    server.use(
      http.get('*/api/shooters/:id/stations', () =>
        HttpResponse.json({
          ...shooterStationsFixture,
          stations: [],
          coverage: { ...none, latest_date: '2026-06-14' },
        }),
      ),
    );
    const user = userEvent.setup();
    renderBreakdown();
    const nudge = (
      await screen.findByText(/^No station sheets for this shooter in the last 8 weeks/)
    ).closest('[role="note"]') as HTMLElement;
    expect(nudge).toHaveTextContent(
      'No station sheets for this shooter in the last 8 weeks (latest: Jun 14).',
    );
    expect(screen.queryByRole('note', { name: 'Station data coverage' })).not.toBeInTheDocument();
    expect(within(nudge).getByRole('button', { name: 'Show the last 12 months' })).toBeVisible();
    await user.click(within(nudge).getByRole('button', { name: 'Show all time' }));
    expect(nudge).toBeInTheDocument();
  });

  it('blames the setup choice when sheets exist but none are since the last reset', async () => {
    server.use(
      http.get('*/api/shooters/:id/stations', ({ request }) => {
        const all = new URL(request.url).searchParams.get('era') === 'all';
        return HttpResponse.json(
          all ? shooterStationsFixture : { ...shooterStationsFixture, stations: [] },
        );
      }),
    );
    const user = userEvent.setup();
    renderBreakdown();
    const nudge = (await screen.findByText(/since the last reset in the last 8 weeks/)).closest(
      '[role="note"]',
    ) as HTMLElement;
    expect(nudge).toHaveTextContent(
      'No station sheets for this shooter since the last reset in the last 8 weeks.',
    );
    await user.click(within(nudge).getByRole('button', { name: 'Show all setups' }));
    expect(await screen.findByRole('region', { name: 'Where you lose targets' })).toBeVisible();
  });

  it('labels the setup choice with the last reset date', async () => {
    server.use(
      http.get('*/api/shooters/:id/stations', () =>
        HttpResponse.json({ ...shooterStationsFixture, last_reset_date: '2026-09-10' }),
      ),
    );
    renderBreakdown();
    expect(
      await screen.findByRole('button', { name: 'Since last reset (Sep 10)' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Each station counts from its own latest reset; Sep 10 is the most recent one\./,
      ),
    ).toBeVisible();
  });

  it('shows an error when the API fails', async () => {
    server.use(
      http.get('*/api/shooters/:id/stations', () => new HttpResponse(null, { status: 500 })),
    );
    renderBreakdown();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not load the station breakdown.',
    );
  });

  it('adds a one-line note on how many Sundays the station data covers', async () => {
    renderBreakdown();
    expect(await screen.findByRole('note', { name: 'Station data coverage' })).toHaveTextContent(
      'Station scores for this shooter: 3 rounds on 2 Sundays in the last 8 weeks (Sep 6, 2026 – Sep 13, 2026).',
    );
  });

  it('shows no coverage note when the shooter has no station sheets', async () => {
    server.use(
      http.get('*/api/shooters/:id/stations', () =>
        HttpResponse.json({ ...shooterStationsFixture, stations: [], coverage: none }),
      ),
    );
    renderBreakdown();
    await screen.findByText('No station sheets for this shooter yet.');
    expect(screen.queryByRole('note', { name: 'Station data coverage' })).not.toBeInTheDocument();
  });

  it('registers as a profile section (C10)', () => {
    expect(profileSection).toEqual({
      id: 'stations',
      title: 'Stations',
      order: 70,
      Component: StationBreakdown,
    });
  });
});
