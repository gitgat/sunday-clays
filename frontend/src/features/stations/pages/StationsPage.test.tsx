import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import {
  captureCsv,
  expectChartControls,
  expectExplainer,
  openFullscreen,
} from '../../../test/charts';
import { stationDetailFixture, stationsFixture } from '../mocks';
import { StationsPage, stationLabels } from './StationsPage';

function renderAt(url = '/stations') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/stations" element={<StationsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function assertFixture(): never {
  throw new Error('the stations fixture has no stations');
}

describe('StationsPage', () => {
  afterEach(() => vi.restoreAllMocks());

  it('summarises every station in a table', async () => {
    renderAt();
    const row = await screen.findByRole('row', { name: /^Station 9\b/ });
    expect(row).toHaveTextContent('50.19%');
    expect(row).toHaveTextContent('43.26%–57.12%');
    expect(row).toHaveTextContent('0.62');
  });

  it('exposes Table and CSV controls on every chart', async () => {
    renderAt();
    await screen.findByText('Wind × station 4');
    const titles = [
      'Hit % by station',
      'Hit % over time',
      'Shooter × station',
      'Station 4 eras',
      'Wind × station 4',
    ];
    for (const title of titles) {
      expectChartControls(screen.getByRole('region', { name: title }));
    }
    expect(screen.getAllByRole('button', { name: 'Table' })).toHaveLength(titles.length);
  });

  it('explains every chart and both tables in plain words', async () => {
    renderAt();
    await screen.findByText('Wind × station 4');
    for (const title of [
      'Hit % by station',
      'Hit % over time',
      'Shooter × station',
      'Station 4 eras',
      'Wind × station 4',
    ]) {
      await expectExplainer(screen.getByRole('region', { name: title }), undefined, { read: true });
    }
    await expectExplainer(
      screen.getByRole('region', { name: 'Station summary section' }),
      'About this table',
      { read: true },
    );
    await expectExplainer(
      screen.getByRole('region', { name: 'Station 4 leaders' }),
      'About these leaders',
    );
  });

  it('shows wind bands with their unit and Sundays', async () => {
    const user = userEvent.setup();
    renderAt();
    const card = await screen.findByRole('region', { name: 'Wind × station 4' });
    await user.click(within(card).getByRole('button', { name: 'Table' }));
    expect(within(card).getByRole('row', { name: /^<10 mph gusts/ })).toHaveTextContent('yes');
    expect(within(card).getByText('20+ mph gusts')).toBeInTheDocument();
    expect(within(card).getByRole('columnheader', { name: 'Sundays' })).toBeInTheDocument();
  });

  it('keeps the heatmap table honest about squares with under 3 rounds', async () => {
    const user = userEvent.setup();
    renderAt();
    const card = await screen.findByRole('region', { name: 'Shooter × station' });
    await user.click(within(card).getByRole('button', { name: 'Table' }));
    expect(within(card).getByRole('row', { name: /^Hadley, Ike 4\b/ })).toHaveTextContent('85.71');
    const short = within(card).getByRole('row', { name: /^Hadley, Ike 9\b/ });
    expect(short).not.toHaveTextContent('50');
    expect(short).toHaveTextContent('not enough rounds yet');
  });

  it('sizes the heatmap by shooters who get a row', async () => {
    const [template] = stationsFixture.matrix;
    const cells = Array.from({ length: 20 }, (_, i) => ({
      ...template,
      shooter_id: i + 1,
      display_name: `Shooter ${i + 1}`,
      n_rounds: i < 2 ? 5 : 1,
    }));
    server.use(
      http.get('*/api/stations', () => HttpResponse.json({ ...stationsFixture, matrix: cells })),
    );
    renderAt();
    const card = await screen.findByRole('region', { name: 'Shooter × station' });
    const chart = await within(card).findByRole(
      'img',
      { name: 'Heatmap of hit % by shooter and station' },
      { timeout: 10_000 },
    );
    expect(chart).toHaveStyle({ height: '320px' });
  });

  it('says so when no shooter has enough rounds for a square', async () => {
    const cells = stationsFixture.matrix.map((c) => ({ ...c, n_rounds: 1 }));
    server.use(
      http.get('*/api/stations', () => HttpResponse.json({ ...stationsFixture, matrix: cells })),
    );
    renderAt();
    expect(
      await screen.findByText('Nobody has shot any station three times in the last 8 weeks.'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Shooter × station' })).not.toBeInTheDocument();
  });

  it('asks for the same era on the station detail', async () => {
    const eras: (string | null)[] = [];
    server.use(
      http.get('*/api/stations/:label', ({ request }) => {
        eras.push(new URL(request.url).searchParams.get('era'));
        return HttpResponse.json(stationDetailFixture);
      }),
    );
    const user = userEvent.setup();
    renderAt();
    await screen.findByText('Wind × station 4');
    expect(eras).toEqual(['current']);
    await user.click(screen.getByRole('button', { name: 'All setups' }));
    await waitFor(() => {
      expect(eras).toContain('all');
    });
  });

  it('shows chart tables and CSV rows as two-decimal percentages', async () => {
    const user = userEvent.setup();
    renderAt();
    const card = await screen.findByRole('region', { name: 'Hit % by station' });
    await user.click(within(card).getByRole('button', { name: 'Table' }));
    const row = within(card).getByRole('row', { name: /^9\b/ });
    expect(row).toHaveTextContent('50.19');
    expect(row).toHaveTextContent('43.26');
  });

  it('gives the shooter × station heatmap a row per shooter', async () => {
    const [template] = stationsFixture.matrix;
    const cells = Array.from({ length: 40 }, (_, i) => ({
      ...template,
      shooter_id: i + 1,
      display_name: `Shooter ${i + 1}`,
    }));
    server.use(
      http.get('*/api/stations', () => HttpResponse.json({ ...stationsFixture, matrix: cells })),
    );
    renderAt();
    const card = await screen.findByRole('region', { name: 'Shooter × station' });
    const chart = await within(card).findByRole(
      'img',
      { name: 'Heatmap of hit % by shooter and station' },
      { timeout: 10_000 },
    );
    expect(chart).toHaveStyle({ height: `${40 * 22 + 96}px` });
  });

  it('labels each era by the reset that started it', async () => {
    const user = userEvent.setup();
    renderAt();
    await screen.findByText('Wind × station 4');
    for (const button of screen.getAllByRole('button', { name: /table/i })) {
      await user.click(button);
    }
    expect(screen.getByText('Original setup')).toBeInTheDocument();
    expect(screen.getByText('Since 2026-09-10')).toBeInTheDocument();
  });

  it('shows dashes where a station has too little data', async () => {
    server.use(
      http.get('*/api/stations', () =>
        HttpResponse.json({
          ...stationsFixture,
          stations: stationsFixture.stations.map((s) => ({
            ...s,
            hit_pct: null,
            ci_low: null,
            ci_high: null,
            clean_rate: null,
            separator: null,
          })),
        }),
      ),
    );
    renderAt();
    const row = await screen.findByRole('row', { name: /^Station 9\b/ });
    expect(row).not.toHaveTextContent('%');
    expect(within(row).getAllByText('—')).toHaveLength(4);
  });

  it('switches the detail panel to the chosen station', async () => {
    const user = userEvent.setup();
    renderAt();
    const picker = await screen.findByRole('group', { name: 'Choose a station' });
    await user.click(within(picker).getByRole('button', { name: 'Station 9' }));
    expect(await screen.findByText('Station 9 eras')).toBeInTheDocument();
    expect(within(picker).getByRole('button', { name: 'Station 9' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('lists station leaders with links to their profiles', async () => {
    renderAt();
    const leaders = await screen.findByRole('region', { name: 'Station 4 leaders' });
    expect(within(leaders).getByRole('link', { name: 'McGinnis, Alvin' })).toHaveAttribute(
      'href',
      '/shooters/7',
    );
  });

  it('lists ten station leaders, then Show all N, and Show fewer folds them back', async () => {
    const leaders = Array.from({ length: 14 }, (_, i) => ({
      shooter_id: 100 + i,
      display_name: `Leader ${String(i + 1).padStart(2, '0')}`,
      hits: 20,
      n_targets: 21,
      n_rounds: 3,
      hit_pct: 0.95 - i / 100,
    }));
    server.use(
      http.get('*/api/stations/:label', () =>
        HttpResponse.json({ ...stationDetailFixture, leaders }),
      ),
    );
    const user = userEvent.setup();
    renderAt();
    const region = await screen.findByRole('region', { name: 'Station 4 leaders' });
    expect(within(region).getAllByRole('listitem')).toHaveLength(10);
    await user.click(within(region).getByRole('button', { name: 'Show all 14' }));
    expect(within(region).getAllByRole('listitem')).toHaveLength(14);
    await user.click(within(region).getByRole('button', { name: 'Show fewer' }));
    expect(within(region).getAllByRole('listitem')).toHaveLength(10);
  });

  it('offers no Show all when there are ten leaders or fewer', async () => {
    renderAt();
    const region = await screen.findByRole('region', { name: 'Station 4 leaders' });
    expect(within(region).queryByRole('button', { name: /Show all/ })).not.toBeInTheDocument();
  });

  it('says how many leaders are tied when the cut at ten splits a tie', async () => {
    const leaders = Array.from({ length: 14 }, (_, i) => ({
      shooter_id: 100 + i,
      display_name: `Leader ${String(i + 1).padStart(2, '0')}`,
      hits: 20,
      n_targets: 21,
      n_rounds: 3,
      hit_pct: i < 8 ? 0.95 - i / 100 : 0.8,
    }));
    server.use(
      http.get('*/api/stations/:label', () =>
        HttpResponse.json({ ...stationDetailFixture, leaders }),
      ),
    );
    const user = userEvent.setup();
    renderAt();
    const region = await screen.findByRole('region', { name: 'Station 4 leaders' });
    expect(within(region).getByText('4 more tied at 80.00%')).toBeVisible();
    await user.click(within(region).getByRole('button', { name: 'Show all 14' }));
    expect(within(region).queryByText(/more tied at/)).not.toBeInTheDocument();
  });

  it('folds the leaders back to ten when the setup choice changes', async () => {
    const leaders = Array.from({ length: 14 }, (_, i) => ({
      shooter_id: 100 + i,
      display_name: `Leader ${String(i + 1).padStart(2, '0')}`,
      hits: 20,
      n_targets: 21,
      n_rounds: 3,
      hit_pct: 0.95 - i / 100,
    }));
    server.use(
      http.get('*/api/stations/:label', () =>
        HttpResponse.json({ ...stationDetailFixture, leaders }),
      ),
    );
    const user = userEvent.setup();
    renderAt();
    const region = await screen.findByRole('region', { name: 'Station 4 leaders' });
    await user.click(within(region).getByRole('button', { name: 'Show all 14' }));
    expect(within(region).getAllByRole('listitem')).toHaveLength(14);
    await user.click(screen.getByRole('button', { name: 'All setups' }));
    await waitFor(() => {
      expect(
        within(screen.getByRole('region', { name: 'Station 4 leaders' })).getAllByRole('listitem'),
      ).toHaveLength(10);
    });
  });

  it('names the empty-window and setup nudges for screen readers', async () => {
    server.use(
      http.get('*/api/stations/:label', () =>
        HttpResponse.json({ ...stationDetailFixture, wind: [], leaders: [] }),
      ),
    );
    renderAt();
    expect(await screen.findAllByRole('note', { name: 'Widen the time window' })).toHaveLength(2);
  });

  it('asks the API for every era when All setups is pressed', async () => {
    const eras: (string | null)[] = [];
    server.use(
      http.get('*/api/stations', ({ request }) => {
        eras.push(new URL(request.url).searchParams.get('era'));
        return HttpResponse.json(stationsFixture);
      }),
    );
    const user = userEvent.setup();
    renderAt();
    await user.click(await screen.findByRole('button', { name: 'All setups' }));
    await waitFor(() => {
      expect(eras).toContain('all');
    });
    expect(eras[0]).toBe('current');
    await user.click(screen.getByRole('button', { name: /Since last reset/ }));
    expect(screen.getByRole('button', { name: /Since last reset/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('passes the global round-type filter to the API', async () => {
    const seen: string[][] = [];
    server.use(
      http.get('*/api/stations', ({ request }) => {
        seen.push(new URL(request.url).searchParams.getAll('round_type'));
        return HttpResponse.json(stationsFixture);
      }),
    );
    renderAt('/stations?rt=super_sporting');
    await screen.findByRole('heading', { level: 1, name: 'Stations' });
    expect(seen[0]).toEqual(['super_sporting']);
  });

  it('shows the weather empty state when a station has no wind cells', async () => {
    server.use(
      http.get('*/api/stations/:label', () =>
        HttpResponse.json({ ...stationDetailFixture, wind: [], leaders: [] }),
      ),
    );
    renderAt();
    const weather = await screen.findByText('No weather data for station 4 in the last 8 weeks.');
    expect(weather.closest('[role="note"]')).toBeInTheDocument();
    expect(
      within(weather.closest('[role="note"]') as HTMLElement).getByRole('button', {
        name: 'Show all time',
      }),
    ).toBeVisible();
    expect(
      screen.getByText('Nobody has shot station 4 three times in the last 8 weeks.'),
    ).toBeInTheDocument();
  });

  it('shows an empty state when the filter removes every station', async () => {
    server.use(
      http.get('*/api/stations', () =>
        HttpResponse.json({
          ...stationsFixture,
          stations: [],
          n_events: 0,
          coverage: { ...stationsFixture.coverage, n_station_sundays: 0 },
        }),
      ),
    );
    renderAt();
    expect(
      await screen.findByText(/^No station sheets in the last 8 weeks \(latest: Sep 13\)/),
    ).toBeInTheDocument();
    // The empty state already says so: the coverage note is not shown a second time.
    expect(screen.queryByRole('note', { name: 'Station data coverage' })).not.toBeInTheDocument();
  });

  it('blames the setup choice, not the window, when sheets exist but no station is current', async () => {
    server.use(
      http.get('*/api/stations', ({ request }) => {
        const all = new URL(request.url).searchParams.get('era') === 'all';
        return HttpResponse.json(all ? stationsFixture : { ...stationsFixture, stations: [] });
      }),
    );
    const user = userEvent.setup();
    renderAt();
    const nudge = (await screen.findByText(/^No station sheets since the last reset/)).closest(
      '[role="note"]',
    ) as HTMLElement;
    expect(nudge).toHaveTextContent('No station sheets since the last reset in the last 8 weeks.');
    expect(nudge).not.toHaveTextContent('latest');
    expect(screen.queryByRole('button', { name: 'Show all time' })).not.toBeInTheDocument();
    await user.click(within(nudge).getByRole('button', { name: 'Show all setups' }));
    await screen.findByRole('row', { name: /^Station 9\b/ });
  });

  it('keeps the plain empty state when there are no station sheets at all', async () => {
    server.use(
      http.get('*/api/stations', () =>
        HttpResponse.json({
          ...stationsFixture,
          stations: [],
          coverage: { ...stationsFixture.coverage, n_station_sundays: 0, latest_date: null },
        }),
      ),
    );
    renderAt();
    expect(await screen.findByText('No station data for this filter.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Show all time' })).not.toBeInTheDocument();
  });

  it('notes how few Sundays the station data covers, from the API', async () => {
    renderAt();
    const note = await screen.findByRole('note', { name: 'Station data coverage' });
    expect(note).toHaveTextContent(
      'Station scores cover 2 of 311 Sundays in the last 8 weeks (Sep 6, 2026 – Sep 13, 2026).',
    );
    expect(note).not.toHaveTextContent('round types you picked');
  });

  it('tells the reader when the round-type filter shapes the counts', async () => {
    renderAt('/stations?rt=super_sporting');
    expect(await screen.findByRole('note', { name: 'Station data coverage' })).toHaveTextContent(
      'round types you picked',
    );
  });

  it('shows an error when the station detail fails', async () => {
    server.use(http.get('*/api/stations/:label', () => new HttpResponse(null, { status: 500 })));
    renderAt();
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load station 4.');
  });

  it('shows an error when the API fails', async () => {
    server.use(http.get('*/api/stations', () => new HttpResponse(null, { status: 500 })));
    renderAt();
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load station data.');
  });

  describe('a lettered station such as 7A', () => {
    const four = stationsFixture.stations[0] ?? assertFixture();
    const seven = { ...four, label: '7', station_no: 7 };
    const sevenA = { ...four, label: '7A', station_no: 7, hit_pct: 0.6, leaders: [] };
    const eight = { ...four, label: '8', station_no: 8 };
    const withSevenA = {
      ...stationsFixture,
      stations: [seven, sevenA, eight],
      by_event: [
        {
          event_date: '2026-09-06',
          label: '8',
          station_no: 8,
          hits: 1,
          n_targets: 2,
          hit_pct: 0.5,
        },
        {
          event_date: '2026-09-06',
          label: '7A',
          station_no: 7,
          hits: 1,
          n_targets: 2,
          hit_pct: 0.5,
        },
        {
          event_date: '2026-09-13',
          label: '7',
          station_no: 7,
          hits: 1,
          n_targets: 2,
          hit_pct: 0.5,
        },
      ],
      matrix: stationsFixture.matrix.map((c, i) => ({
        ...c,
        label: i === 0 ? '7A' : '8',
        station_no: i === 0 ? 7 : 8,
      })),
    };

    it('is its own row and button, after 7', async () => {
      server.use(http.get('*/api/stations', () => HttpResponse.json(withSevenA)));
      renderAt();
      await screen.findByRole('row', { name: /^Station 7A\b/ });
      expect(screen.getAllByRole('rowheader').map((h) => h.textContent)).toEqual([
        'Station 7',
        'Station 7A',
        'Station 8',
      ]);
      const picker = screen.getByRole('group', { name: 'Choose a station' });
      expect(
        within(picker)
          .getAllByRole('button')
          .map((b) => b.textContent),
      ).toEqual(['Station 7', 'Station 7A', 'Station 8']);
    });

    it('opens its own detail from the picker and puts the label in the URL', async () => {
      const asked: string[] = [];
      server.use(
        http.get('*/api/stations', () => HttpResponse.json(withSevenA)),
        http.get('*/api/stations/:label', ({ params }) => {
          asked.push(String(params.label));
          return HttpResponse.json({ ...stationDetailFixture, label: params.label, station_no: 7 });
        }),
      );
      const user = userEvent.setup();
      renderAt();
      await screen.findByText('Wind × station 7');
      await user.click(screen.getByRole('button', { name: 'Station 7A' }));
      expect(await screen.findByText('Wind × station 7A')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Station 7A' })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
      expect(screen.getByRole('region', { name: 'Station 7A leaders' })).toBeInTheDocument();
      expect(asked).toContain('7A');
    });

    it('opens on ?st=7A, and an old ?st=7 link still opens station 7', async () => {
      server.use(http.get('*/api/stations', () => HttpResponse.json(withSevenA)));
      const first = renderAt('/stations?st=7A');
      expect(await screen.findByText('Wind × station 7A')).toBeInTheDocument();
      first.unmount();
      renderAt('/stations?st=7');
      expect(await screen.findByText('Wind × station 7')).toBeInTheDocument();
    });

    it('opens a lower-case or padded ?st=7a link on station 7A', async () => {
      server.use(http.get('*/api/stations', () => HttpResponse.json(withSevenA)));
      renderAt('/stations?st=%207a');
      expect(await screen.findByText('Wind × station 7A')).toBeInTheDocument();
    });

    it('falls back to the first station for a label that is not on the page', async () => {
      server.use(http.get('*/api/stations', () => HttpResponse.json(withSevenA)));
      renderAt('/stations?st=7B');
      expect(await screen.findByText('Wind × station 7')).toBeInTheDocument();
    });

    it('lists 7A in the chart table and CSV rows by label', async () => {
      server.use(http.get('*/api/stations', () => HttpResponse.json(withSevenA)));
      const user = userEvent.setup();
      renderAt();
      const card = await screen.findByRole('region', { name: 'Hit % by station' });
      await user.click(within(card).getByRole('button', { name: 'Table' }));
      const cells = within(card)
        .getAllByRole('row')
        .slice(1)
        .map((r) => within(r).getAllByRole('cell')[0]?.textContent);
      expect(cells).toEqual(['7', '7A', '8']);
    });
  });

  describe('Hit % over time: the card follows the window, fullscreen and CSV cover every Sunday', () => {
    /** The fixture's two Sundays, plus one from early 2025 that the default window leaves off. */
    const old = {
      event_date: '2025-01-05',
      label: '4',
      station_no: 4,
      hits: 50,
      n_targets: 90,
      hit_pct: 0.55,
    };
    const withOldSunday = {
      ...stationsFixture,
      by_event: [old, ...stationsFixture.by_event],
    };
    /** A request with a `since` is the windowed page; without one it is the full-history fetch. */
    const windowedOrAll = http.get('*/api/stations', ({ request }) =>
      HttpResponse.json(
        new URL(request.url).searchParams.has('since') ? stationsFixture : withOldSunday,
      ),
    );
    const rowCount = (el: HTMLElement) => within(el).getAllByRole('row').length;

    it('shows the windowed Sundays inline and every Sunday in fullscreen', async () => {
      server.use(windowedOrAll);
      const user = userEvent.setup();
      renderAt('/stations?sttime=table');
      const card = await screen.findByRole('region', { name: 'Hit % over time' });
      expect(rowCount(card)).toBe(1 + stationsFixture.by_event.length);
      const dialog = await openFullscreen(user, card, 'Hit % over time');
      await waitFor(() => {
        expect(rowCount(dialog)).toBe(1 + withOldSunday.by_event.length);
      });
      expect(within(dialog).getByText('All time')).toBeInTheDocument();
      expect(
        within(dialog).getByText('Every Sunday with a station sheet, whatever the time window.'),
      ).toBeInTheDocument();
    });

    it('downloads every Sunday as CSV, not just the window', async () => {
      server.use(windowedOrAll);
      const csv = captureCsv();
      const user = userEvent.setup();
      renderAt('/stations?sttime=table');
      const card = await screen.findByRole('region', { name: 'Hit % over time' });
      await user.click(within(card).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toEqual(['station-difficulty.csv']));
      expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(
        1 + withOldSunday.by_event.length,
      );
    });
  });

  describe('the header time window', () => {
    const calls: URLSearchParams[] = [];
    const record = http.get('*/api/stations', ({ request }) => {
      calls.push(new URL(request.url).searchParams);
      return HttpResponse.json(stationsFixture);
    });

    it('sends the 8 week window as since and as_of, and names it in plain words', async () => {
      calls.length = 0;
      server.use(record);
      renderAt();
      await screen.findByRole('heading', { level: 1, name: 'Stations' });
      expect(calls[0]?.get('since')).toBe('2026-08-03');
      expect(calls[0]?.get('as_of')).toBe('2026-09-27');
      expect(screen.getByRole('note', { name: 'Setups and dates shown' })).toHaveTextContent(
        'Current setups · Last 8 weeks · Aug 3 – Sep 27',
      );
      expect(screen.getByRole('note', { name: 'Station data coverage' })).toHaveTextContent(
        'Station scores cover 2 of 311 Sundays in the last 8 weeks',
      );
    });

    it('sends a custom range as given, and All sends no dates', async () => {
      calls.length = 0;
      server.use(record);
      const { unmount } = renderAt('/stations?w=2026-09-01..2026-09-20');
      await screen.findByRole('heading', { level: 1, name: 'Stations' });
      expect(calls[0]?.get('since')).toBe('2026-09-01');
      expect(calls[0]?.get('as_of')).toBe('2026-09-20');
      expect(screen.getByRole('note', { name: 'Setups and dates shown' })).toHaveTextContent(
        'Current setups · Sep 1, 2026 – Sep 20, 2026',
      );
      unmount();
      calls.length = 0;
      renderAt('/stations?w=all&era=all');
      await screen.findByRole('heading', { level: 1, name: 'Stations' });
      expect(calls[0]?.has('since')).toBe(false);
      expect(calls[0]?.has('as_of')).toBe(false);
      expect(screen.getByRole('note', { name: 'Setups and dates shown' })).toHaveTextContent(
        'All setups · All time',
      );
    });

    it('sends the window to the station detail too', async () => {
      const seen: URLSearchParams[] = [];
      server.use(
        http.get('*/api/stations/:label', ({ request }) => {
          seen.push(new URL(request.url).searchParams);
          return HttpResponse.json(stationDetailFixture);
        }),
      );
      renderAt('/stations?w=6m');
      await screen.findByText('Wind × station 4');
      expect(seen[0]?.get('since')).toBe('2026-03-28');
      expect(seen[0]?.get('as_of')).toBe('2026-09-27');
    });

    it('waits for the latest Sunday instead of asking without dates', async () => {
      calls.length = 0;
      server.use(
        record,
        http.get('*/api/meta', () => new HttpResponse(null, { status: 500 })),
      );
      renderAt();
      expect(await screen.findByRole('alert')).toHaveTextContent('Could not load station data.');
      expect(calls).toHaveLength(0);
    });

    it('an All window still loads when the latest Sunday lookup fails', async () => {
      server.use(http.get('*/api/meta', () => new HttpResponse(null, { status: 500 })));
      renderAt('/stations?w=all');
      expect(await screen.findByRole('row', { name: /^Station 9\b/ })).toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('labels the setup choice with the last reset date', async () => {
      server.use(
        http.get('*/api/stations', () =>
          HttpResponse.json({ ...stationsFixture, last_reset_date: '2026-09-10' }),
        ),
      );
      renderAt();
      expect(
        await screen.findByRole('button', { name: 'Since last reset (Sep 10)' }),
      ).toHaveAttribute('aria-pressed', 'true');
      expect(screen.getByRole('button', { name: 'All setups' })).toBeInTheDocument();
    });

    it('says no sheets fall in the window, names the latest, and offers 12M and All', async () => {
      const wide = vi.fn();
      server.use(
        http.get('*/api/stations', ({ request }) => {
          const wideWindow = new URL(request.url).searchParams.get('since') !== '2026-08-03';
          if (wideWindow) wide();
          return HttpResponse.json(
            wideWindow
              ? stationsFixture
              : {
                  ...stationsFixture,
                  stations: [],
                  by_event: [],
                  matrix: [],
                  n_events: 0,
                  coverage: {
                    n_station_sundays: 0,
                    first_date: null,
                    last_date: null,
                    n_scored_sundays: 8,
                    latest_date: '2026-09-13',
                  },
                },
          );
        }),
      );
      const user = userEvent.setup();
      renderAt();
      const nudge = (await screen.findByText(/^No station sheets in the last 8 weeks/)).closest(
        '[role="note"]',
      ) as HTMLElement;
      expect(nudge).toHaveTextContent('No station sheets in the last 8 weeks (latest: Sep 13).');
      await user.click(within(nudge).getByRole('button', { name: 'Show the last 12 months' }));
      await screen.findByRole('row', { name: /^Station 9\b/ });
      expect(wide).toHaveBeenCalled();
      expect(screen.queryByText(/^No station sheets in the last 8 weeks/)).not.toBeInTheDocument();
    });

    it('offers only All when the window is already 12 months, and nothing on All', async () => {
      const empty = {
        ...stationsFixture,
        stations: [],
        coverage: {
          ...stationsFixture.coverage,
          n_station_sundays: 0,
          first_date: null,
          last_date: null,
        },
      };
      server.use(http.get('*/api/stations', () => HttpResponse.json(empty)));
      const { unmount } = renderAt('/stations?w=12m');
      const nudge = (await screen.findByText(/^No station sheets in the last 12 months/)).closest(
        '[role="note"]',
      ) as HTMLElement;
      expect(within(nudge).getAllByRole('button')).toHaveLength(1);
      expect(within(nudge).getByRole('button', { name: 'Show all time' })).toBeInTheDocument();
      unmount();
      renderAt('/stations?w=all');
      const bare = (await screen.findByText(/^No station sheets so far/)).closest(
        '[role="note"]',
      ) as HTMLElement;
      expect(bare).toHaveTextContent('No station sheets so far (latest: Sep 13).');
      expect(within(bare).queryAllByRole('button')).toHaveLength(0);
    });

    it('says who has not shot a station three times in the period', async () => {
      server.use(
        http.get('*/api/stations/:label', () =>
          HttpResponse.json({ ...stationDetailFixture, wind: [], leaders: [] }),
        ),
      );
      renderAt('/stations?w=3m');
      expect(
        await screen.findByText('Nobody has shot station 4 three times in the last 3 months.'),
      ).toBeInTheDocument();
      expect(
        screen.getByText('No weather data for station 4 in the last 3 months.'),
      ).toBeInTheDocument();
    });
  });
});

describe('stationLabels', () => {
  it("maps an insight's station numbers to the chart's categories", () => {
    expect(stationLabels(['5', '12', '7A', 'St 3'])).toEqual(['St 5', 'St 12', 'St 7A', 'St 3']);
  });
});
