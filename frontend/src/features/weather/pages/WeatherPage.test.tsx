import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import {
  captureCsv,
  chartOptionIn,
  expectChartControls,
  expectExplainer,
  openFullscreen,
} from '../../../test/charts';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { getInstanceByDom } from 'echarts/core';
import { renderWithProviders } from '../../../test/render';
import { WEATHER_EFFECTS, WEATHER_EVENTS, WEATHER_SENSITIVITY, WEATHER_TURNOUT } from '../mocks';
import { WeatherPage } from './WeatherPage';

const CHARTS = [
  'Difficulty and weather',
  'Wind rose',
  'Scores by conditions',
  'Turnout by conditions',
  'Weather sensitivity',
];

function serveAll(effectsUrls: string[] = [], turnoutUrls: string[] = [], anchor = '2026-09-27') {
  server.use(
    http.get('*/api/meta', () => HttpResponse.json({ last_score_date: anchor })),
    http.get('*/api/weather/events', () => HttpResponse.json(WEATHER_EVENTS)),
    http.get('*/api/weather/effects', ({ request }) => {
      effectsUrls.push(request.url);
      return HttpResponse.json(WEATHER_EFFECTS);
    }),
    http.get('*/api/weather/sensitivity', () => HttpResponse.json(WEATHER_SENSITIVITY)),
    http.get('*/api/weather/turnout', ({ request }) => {
      turnoutUrls.push(request.url);
      return HttpResponse.json(WEATHER_TURNOUT);
    }),
  );
}

// The 2018 Sunday has no difficulty in the shared mock; give it one so the scatter has a fourth
// point outside the default window.
const OLD_SUNDAY_WITH_DIFFICULTY = WEATHER_EVENTS.map((e) =>
  e.event_date === '2018-12-30' ? { ...e, difficulty: 0.5, median: 30, has_scores: true } : e,
);

describe('WeatherPage', () => {
  afterEach(() => vi.restoreAllMocks());

  it('every data chart exposes Table and CSV controls', async () => {
    serveAll();
    renderWithProviders(<WeatherPage />);
    for (const title of CHARTS) {
      const chart = await screen.findByRole('region', { name: title });
      expectChartControls(chart);
    }
    expect(screen.getByText(/club model over all 84 Sundays/)).toBeInTheDocument();
  });

  it(
    'shows a plain note instead of bars when a measure has no spread, and keeps the picker',
    async () => {
      serveAll();
      server.use(
        http.get('*/api/weather/sensitivity', () =>
          HttpResponse.json({
            ...WEATHER_SENSITIVITY,
            tau2: [{ covariate: 'temp_f', tau2: 0 }],
            shooters: WEATHER_SENSITIVITY.shooters.map((s) => ({
              ...s,
              terms: s.terms.map((t) =>
                t.covariate === 'temp_f' ? { ...t, shrunk: 0, per_unit: 0 } : t,
              ),
            })),
          }),
        ),
      );
      const { user } = renderWithProviders(<WeatherPage />, { route: '/?wsc=temp_f' });
      const card = await screen.findByRole('region', { name: 'Weather sensitivity' });
      expect(
        await within(card).findByText(/No one's scores move with temperature more than chance/),
      ).toBeInTheDocument();
      expect(
        within(card).getByText(/everyone's estimate for temperature rounds to zero/),
      ).toBeInTheDocument();
      const img = await within(card).findByRole(
        'img',
        { name: 'No weather sensitivity to show for temperature' },
        LAZY_CHART,
      );
      expect(within(card).queryByRole('img', { name: /Bar chart/ })).not.toBeInTheDocument();
      await waitFor(() => expect(getInstanceByDom(img)).toBeDefined(), LAZY_CHART);
      expect(chartOptionIn(card, /weather sensitivity/).series ?? []).toEqual([]);
      expectChartControls(card);
      // Nothing to draw, so there is nothing more to show in fullscreen either.
      expect(within(card).queryByRole('button', { name: 'Fullscreen' })).not.toBeInTheDocument();
      await user.click(within(card).getByRole('button', { name: 'Table' }));
      expect(within(card).getAllByRole('row')).toHaveLength(3);
      await user.selectOptions(
        within(card).getByRole('combobox', { name: 'Sensitivity to' }),
        'gust_mph',
      );
      expect(within(card).queryByText(/No one's scores move/)).not.toBeInTheDocument();
      expect(within(card).getByRole('button', { name: 'Fullscreen' })).toBeInTheDocument();
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'draws the sensitivity bars with no side slider when a measure has spread',
    async () => {
      serveAll();
      renderWithProviders(<WeatherPage />, { route: '/?wsc=gust_mph' });
      const card = await screen.findByRole('region', { name: 'Weather sensitivity' });
      const img = await within(card).findByRole('img', { name: /weather sensitivity/ }, LAZY_CHART);
      await waitFor(() => expect(getInstanceByDom(img)).toBeDefined(), LAZY_CHART);
      const option = chartOptionIn(card, /weather sensitivity/);
      expect(option.dataZoom ?? []).toEqual([]);
      expect(option.xAxis).toMatchObject([{ name: 'Targets gained or lost' }]);
    },
    LAZY_TEST_TIMEOUT,
  );

  it('shows the empty state before any Sunday has weather', async () => {
    server.use(http.get('*/api/weather/events', () => HttpResponse.json([])));
    renderWithProviders(<WeatherPage />);
    expect(await screen.findByRole('heading', { name: 'No weather data yet' })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Wind rose' })).not.toBeInTheDocument();
  });

  it('applies the global round-type filter to events and the effects request', async () => {
    const urls: string[] = [];
    serveAll(urls);
    renderWithProviders(<WeatherPage />, { route: '/?rt=super_sporting' });
    expect(
      await screen.findByText('1 of 1 Sundays in the last 8 weeks match.'),
    ).toBeInTheDocument();
    await screen.findByRole('region', { name: 'Scores by conditions' });
    expect(new URL(urls[0] ?? '').searchParams.getAll('round_type')).toEqual(['super_sporting']);
  });

  it('switches the grouping of the band charts and keeps it in the URL', async () => {
    serveAll();
    const { user, router } = renderWithProviders(<WeatherPage />);
    const scores = await screen.findByRole('region', { name: 'Scores by conditions' });
    await user.selectOptions(
      within(scores).getByRole('combobox', { name: 'Group scores by' }),
      'condition',
    );
    expect(router.state.location.search).toBe('?wdim=condition');
    await user.click(within(scores).getByRole('button', { name: 'Table' }));
    expect(within(scores).getByRole('cell', { name: 'Rain' })).toBeInTheDocument();
    const fit = screen.getByRole('region', { name: 'Difficulty and weather' });
    await user.selectOptions(
      within(fit).getByRole('combobox', { name: 'Weather measure' }),
      'temp_f',
    );
    const sensitivity = screen.getByRole('region', { name: 'Weather sensitivity' });
    await user.selectOptions(
      within(sensitivity).getByRole('combobox', { name: 'Sensitivity to' }),
      'precip_in',
    );
    // ChartFrame keeps its Table toggle in the URL too (C10: useUrlState(urlKey)), so the
    // click above added wb=table between the two selects.
    expect(router.state.location.search).toBe('?wdim=condition&wb=table&wx=temp_f&wsc=precip_in');
  });

  it('offers Time of year, winter to fall, in both band charts', async () => {
    serveAll();
    const { user, router } = renderWithProviders(<WeatherPage />);
    const scores = await screen.findByRole('region', { name: 'Scores by conditions' });
    await user.selectOptions(
      within(scores).getByRole('combobox', { name: 'Group scores by' }),
      'Time of year',
    );
    expect(router.state.location.search).toBe('?wdim=time_of_year');
    await user.click(within(scores).getByRole('button', { name: 'Table' }));
    expect(within(scores).getByRole('cell', { name: 'Summer' })).toBeInTheDocument();
    expect(within(scores).getByRole('cell', { name: 'Fall' })).toBeInTheDocument();
    const turnout = screen.getByRole('region', { name: 'Turnout by conditions' });
    expect(
      within(within(turnout).getByRole('combobox', { name: 'Group turnout by' }))
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Temperature', 'Wind', 'Rain', 'Conditions', 'Time of year']);
    await user.click(within(turnout).getByRole('button', { name: 'Table' }));
    expect(within(turnout).getByRole('cell', { name: 'Winter' })).toBeInTheDocument();
  });

  it('gives each linked grouping picker its own name and a unit in each sensitivity option', async () => {
    serveAll();
    renderWithProviders(<WeatherPage />);
    const turnout = await screen.findByRole('region', { name: 'Turnout by conditions' });
    expect(within(turnout).getByRole('combobox', { name: 'Group turnout by' })).toBeInTheDocument();
    const sensitivity = screen.getByRole('region', { name: 'Weather sensitivity' });
    const picker = within(sensitivity).getByRole('combobox', { name: 'Sensitivity to' });
    expect(
      within(picker)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Temperature, per 10 °F', 'Gusts, per 10 mph', 'Rain, per 0.1 in']);
  });

  it('keeps the pickers out of the card header row so titles are never squeezed', async () => {
    serveAll();
    renderWithProviders(<WeatherPage />);
    for (const [title, picker] of [
      ['Difficulty and weather', 'Weather measure'],
      ['Scores by conditions', 'Group scores by'],
      ['Turnout by conditions', 'Group turnout by'],
      ['Weather sensitivity', 'Sensitivity to'],
    ] as const) {
      const region = await screen.findByRole('region', { name: title });
      const header = region.querySelector('header');
      expect(within(header as HTMLElement).queryByRole('combobox', { name: picker })).toBeNull();
      expect(within(region).getByRole('combobox', { name: picker })).toBeInTheDocument();
    }
  });

  it('follows the time window: the last 8 weeks by default, all history on request', async () => {
    const effects: string[] = [];
    const turnout: string[] = [];
    serveAll(effects, turnout);
    const first = renderWithProviders(<WeatherPage />);
    await screen.findByRole('region', { name: 'Turnout by conditions' });
    const params = (url: string | undefined) => Object.fromEntries(new URL(url ?? '').searchParams);
    expect(params(effects.at(-1))).toMatchObject({ from: '2026-08-03', to: '2026-09-27' });
    expect(params(turnout.at(-1))).toEqual({ from: '2026-08-03', to: '2026-09-27' });
    expect(screen.getByText('3 of 3 Sundays in the last 8 weeks match.')).toBeInTheDocument();
    first.unmount();

    const all: string[] = [];
    serveAll(all, []);
    renderWithProviders(<WeatherPage />, { route: '/?w=all' });
    await screen.findByRole('region', { name: 'Scores by conditions' });
    expect(params(all.at(-1))).toEqual({ to: '2026-09-27' });
    expect(screen.getByText('3 of 3 Sundays on record match.')).toBeInTheDocument();
  });

  it('narrows the per-Sunday charts to the window', async () => {
    serveAll([], [], '2026-08-20');
    renderWithProviders(<WeatherPage />, { route: '/?w=3m' });
    // Only 2026-08-16 lies in 2026-05-21..2026-08-20.
    expect(
      await screen.findByText('1 of 1 Sundays in the last 3 months match.'),
    ).toBeInTheDocument();
  });

  it('says when the window holds no Sundays with weather', async () => {
    serveAll([], [], '2030-01-06');
    renderWithProviders(<WeatherPage />);
    expect(
      await screen.findByText('No Sundays in the last 8 weeks. Weather patterns need more.'),
    ).toBeInTheDocument();
  });

  it('opens on the last 12 months when the URL has no window, and an explicit w wins', async () => {
    const effects: string[] = [];
    serveAll(effects);
    const first = renderWithProviders(<WeatherPage />, { route: '/weather' });
    await screen.findByRole('region', { name: 'Scores by conditions' });
    expect(new URL(effects.at(-1) ?? '').searchParams.get('from')).toBe('2025-09-28');
    expect(screen.getByText('3 of 3 Sundays in the last 12 months match.')).toBeInTheDocument();
    first.unmount();
    renderWithProviders(<WeatherPage />, { route: '/weather?w=8w' });
    expect(
      await screen.findByText('3 of 3 Sundays in the last 8 weeks match.'),
    ).toBeInTheDocument();
  });

  it('nudges a thin window with the count and 12M / All buttons that widen it', async () => {
    serveAll();
    const { user, router } = renderWithProviders(<WeatherPage />, { route: '/weather?w=8w' });
    expect(
      await screen.findByText('Only 3 Sundays in the last 8 weeks. Weather patterns need more.'),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Show the last 12 months' }));
    // 12M is Weather's own default, so it is the URL without a w.
    expect(router.state.location.search).toBe('');
    expect(
      await screen.findByText('Only 3 Sundays in the last 12 months. Weather patterns need more.'),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Show all time' }));
    expect(router.state.location.search).toBe('?w=all');
  });

  it('explains every chart and the explorer, tagged with the data it covers', async () => {
    serveAll();
    renderWithProviders(<WeatherPage />);
    const windowed = [
      'Difficulty and weather',
      'Wind rose',
      'Scores by conditions',
      'Turnout by conditions',
    ];
    for (const title of windowed) {
      const region = await screen.findByRole('region', { name: title });
      expect(within(region).getByText(/^Last 8 weeks( · .+)?$/)).toBeInTheDocument();
      await expectExplainer(region, 'About this chart');
    }
    const sensitivity = screen.getByRole('region', { name: 'Weather sensitivity' });
    expect(within(sensitivity).getByText('All time')).toBeInTheDocument();
    await expectExplainer(sensitivity, 'About this chart');
    const explorer = screen.getByRole('region', { name: 'Conditions explorer' });
    expect(within(explorer).getByText(/^Last 8 weeks( · .+)?$/)).toBeInTheDocument();
    await expectExplainer(explorer, 'About this explorer');
  });

  it('explains a missing model', async () => {
    serveAll();
    server.use(
      http.get('*/api/weather/effects', () =>
        HttpResponse.json({ ...WEATHER_EFFECTS, model: null }),
      ),
    );
    renderWithProviders(<WeatherPage />);
    expect(
      await screen.findByText(/Not enough Sundays with weather for a club model yet/),
    ).toBeInTheDocument();
  });

  it('reports failed requests per chart and for the page', async () => {
    const failed = () =>
      HttpResponse.json({ error: { code: 'internal', message: 'x' } }, { status: 500 });
    server.use(
      http.get('*/api/weather/events', () => HttpResponse.json(WEATHER_EVENTS)),
      http.get('*/api/weather/effects', failed),
      http.get('*/api/weather/sensitivity', failed),
      http.get('*/api/weather/turnout', failed),
    );
    renderWithProviders(<WeatherPage />);
    expect(await screen.findByText('Could not load weather effects.')).toBeInTheDocument();
    expect(await screen.findByText('Could not load turnout.')).toBeInTheDocument();
    expect(await screen.findByText('Could not load weather sensitivity.')).toBeInTheDocument();
  });

  it('says nothing is scored yet, rather than loading for ever, when no Sunday has scores', async () => {
    serveAll();
    server.use(http.get('*/api/meta', () => HttpResponse.json({ last_score_date: null })));
    renderWithProviders(<WeatherPage />);
    expect(await screen.findByRole('heading', { name: 'No scored Sundays yet' })).toBeVisible();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Wind rose' })).not.toBeInTheDocument();
  });

  it('waits for the window anchor before drawing the charts', async () => {
    serveAll();
    server.use(http.get('*/api/meta', () => new Promise(() => undefined)));
    renderWithProviders(<WeatherPage />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.getByRole('status')).toHaveTextContent('Loading weather…');
    expect(screen.queryByRole('region', { name: 'Wind rose' })).not.toBeInTheDocument();
  });

  it('shows an error, not an endless Loading, when the latest Sunday cannot be loaded', async () => {
    serveAll();
    server.use(
      http.get('*/api/meta', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'x' } }, { status: 500 }),
      ),
    );
    renderWithProviders(<WeatherPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the time window.');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('shows one message, not empty charts, when the window has no Sundays', async () => {
    serveAll();
    renderWithProviders(<WeatherPage />, { route: '/?w=2010-01-03..2010-02-07' });
    expect(await screen.findByRole('note')).toHaveTextContent(
      'No Sundays in Jan 3, 2010 – Feb 7, 2010.',
    );
    expect(screen.getByRole('button', { name: 'Show all time' })).toBeVisible();
    for (const title of ['Difficulty and weather', 'Wind rose', 'Scores by conditions']) {
      expect(screen.queryByRole('region', { name: title })).not.toBeInTheDocument();
    }
    // The all-Sundays chart is not the window's to empty.
    expect(await screen.findByRole('region', { name: 'Weather sensitivity' })).toBeVisible();
  });

  it('reports a failed events request', async () => {
    server.use(
      http.get('*/api/weather/events', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'x' } }, { status: 500 }),
      ),
    );
    renderWithProviders(<WeatherPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load weather.');
  });

  describe('full data in fullscreen and CSV', () => {
    const rowCount = (el: HTMLElement) => within(el).getAllByRole('row').length;

    it('difficulty scatter: the fullscreen table and CSV hold every Sunday, the card only the window', async () => {
      serveAll();
      server.use(
        http.get('*/api/weather/events', () => HttpResponse.json(OLD_SUNDAY_WITH_DIFFICULTY)),
      );
      const csv = captureCsv();
      const { user } = renderWithProviders(<WeatherPage />);
      const card = await screen.findByRole('region', { name: 'Difficulty and weather' });
      await user.click(within(card).getByRole('button', { name: 'Table' }));
      expect(rowCount(card)).toBe(1 + 3);
      const dialog = await openFullscreen(user, card, 'Difficulty and weather');
      expect(within(dialog).getByText('Every Sunday with weather.')).toBeInTheDocument();
      expect(rowCount(dialog)).toBe(1 + 4);
      await user.click(within(card).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toEqual(['weather-difficulty.csv']));
      expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(1 + 4);
    });

    it('difficulty scatter keeps the round-type filter on the full data', async () => {
      serveAll();
      server.use(
        http.get('*/api/weather/events', () => HttpResponse.json(OLD_SUNDAY_WITH_DIFFICULTY)),
      );
      const { user } = renderWithProviders(<WeatherPage />, { route: '/?rt=sporting' });
      const card = await screen.findByRole('region', { name: 'Difficulty and weather' });
      await user.click(within(card).getByRole('button', { name: 'Table' }));
      const dialog = await openFullscreen(user, card, 'Difficulty and weather');
      // sporting: 2018-12-30, 2026-08-16, 2026-09-27
      expect(rowCount(dialog)).toBe(1 + 3);
    });

    it('wind rose: the full data counts every Sunday with a wind direction', async () => {
      serveAll();
      server.use(
        http.get('*/api/weather/events', () => HttpResponse.json(OLD_SUNDAY_WITH_DIFFICULTY)),
      );
      const csv = captureCsv();
      const { user } = renderWithProviders(<WeatherPage />);
      const card = await screen.findByRole('region', { name: 'Wind rose' });
      await user.click(within(card).getByRole('button', { name: 'Table' }));
      // Inline: the window has no Sunday with wind from the north; the 2018 Sunday is one.
      expect(within(card).getByRole('row', { name: /^N 0/ })).toBeInTheDocument();
      const dialog = await openFullscreen(user, card, 'Wind rose');
      expect(within(dialog).getByText('Every Sunday with weather.')).toBeInTheDocument();
      expect(within(dialog).getByRole('row', { name: /^N 1 30/ })).toBeInTheDocument();
      await user.click(within(card).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toEqual(['weather-wind-rose.csv']));
      const lines = (await csv.text()).trimEnd().split('\r\n');
      expect(lines).toHaveLength(1 + 8);
      expect(lines).toContain('N,1,30');
    });

    it('scores by conditions: fullscreen and CSV fetch with no window and the round-type filter', async () => {
      const effects: string[] = [];
      serveAll(effects);
      // The unwindowed fetch sees one more band than the windowed one.
      const extra = { ...WEATHER_EFFECTS.bands[0], band: '85+', mean_score: 20 };
      server.use(
        http.get('*/api/weather/effects', ({ request }) => {
          effects.push(request.url);
          const windowed = new URL(request.url).searchParams.has('from');
          return HttpResponse.json({
            ...WEATHER_EFFECTS,
            bands: windowed ? WEATHER_EFFECTS.bands : [...WEATHER_EFFECTS.bands, extra],
          });
        }),
      );
      const csv = captureCsv();
      const { user } = renderWithProviders(<WeatherPage />, { route: '/?rt=sporting&wb=table' });
      const card = await screen.findByRole('region', { name: 'Scores by conditions' });
      await waitFor(() => expect(effects).toHaveLength(1));
      const inline = within(card).getAllByRole('row').length;
      const dialog = await openFullscreen(user, card, 'Scores by conditions');
      expect(
        await within(dialog).findByText('Every Sunday with weather on record.'),
      ).toBeInTheDocument();
      const full = new URL(effects.at(-1) ?? '');
      expect(effects).toHaveLength(2);
      expect(full.searchParams.has('from')).toBe(false);
      expect(full.searchParams.has('to')).toBe(false);
      expect(full.searchParams.getAll('round_type')).toEqual(['sporting']);
      expect(within(dialog).getAllByRole('row')).toHaveLength(inline + 1);
      await user.click(within(card).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toEqual(['weather-scores-by-band.csv']));
      expect(effects).toHaveLength(2);
      expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(inline + 1);
    });

    it('turnout by conditions: fullscreen and CSV fetch with no window', async () => {
      const turnout: string[] = [];
      serveAll([], turnout);
      // The unwindowed fetch sees one more band than the windowed one.
      const extra = { ...WEATHER_TURNOUT[0], band: '85+' };
      server.use(
        http.get('*/api/weather/turnout', ({ request }) => {
          turnout.push(request.url);
          const windowed = new URL(request.url).searchParams.has('from');
          return HttpResponse.json(windowed ? WEATHER_TURNOUT : [...WEATHER_TURNOUT, extra]);
        }),
      );
      const csv = captureCsv();
      const { user } = renderWithProviders(<WeatherPage />, { route: '/?wt=table' });
      const card = await screen.findByRole('region', { name: 'Turnout by conditions' });
      await waitFor(() => expect(turnout).toHaveLength(1));
      const inline = within(card).getAllByRole('row').length;
      await user.click(within(card).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toEqual(['weather-turnout.csv']));
      expect(turnout).toHaveLength(2);
      expect([...new URL(turnout.at(-1) ?? '').searchParams.keys()]).toEqual([]);
      expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(inline + 1);
      const dialog = await openFullscreen(user, card, 'Turnout by conditions');
      expect(
        await within(dialog).findByText('Every Sunday with weather on record.'),
      ).toBeInTheDocument();
      expect(within(dialog).getAllByRole('row')).toHaveLength(inline + 1);
    });
    it(
      'weather sensitivity: fullscreen draws every shooter, the card only the 12 biggest',
      async () => {
        const many = Array.from({ length: 15 }, (_, i) => ({
          shooter_id: 1000 + i,
          display_name: `Shooter ${String(i).padStart(2, '0')}`,
          n_rounds: 20,
          terms: [
            {
              covariate: 'gust_mph' as const,
              beta: 0.1,
              se: 0.1,
              shrunk: 0.1,
              per_unit: 0.1 + i / 100,
            },
          ],
        }));
        serveAll();
        server.use(
          http.get('*/api/weather/sensitivity', () =>
            HttpResponse.json({ ...WEATHER_SENSITIVITY, shooters: many }),
          ),
        );
        const csv = captureCsv();
        const { user } = renderWithProviders(<WeatherPage />, { route: '/?wsc=gust_mph' });
        const card = await screen.findByRole('region', { name: 'Weather sensitivity' });
        await within(card).findByRole('img', { name: /weather sensitivity/ }, LAZY_CHART);
        const bars = (o: ReturnType<typeof chartOptionIn>) =>
          ((o.yAxis as { data: string[] }[])[0] as { data: string[] }).data.length;
        expect(bars(chartOptionIn(card, /weather sensitivity/))).toBe(12);
        const dialog = await openFullscreen(user, card, 'Weather sensitivity');
        await within(dialog).findByRole('img', { name: /weather sensitivity/ }, LAZY_CHART);
        await waitFor(() => expect(bars(chartOptionIn(dialog, /weather sensitivity/))).toBe(15));
        await user.click(within(card).getByRole('button', { name: 'CSV' }));
        await waitFor(() => expect(csv.names).toEqual(['weather-sensitivity.csv']));
        expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(1 + 15);
      },
      LAZY_TEST_TIMEOUT,
    );
  });
});
