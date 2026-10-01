import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  captureCsv,
  chartOptionIn,
  expectChartControls,
  expectExplainer,
  openFullscreen,
} from '../../../test/charts';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { createTestQueryClient, renderWithProviders } from '../../../test/render';
import { windowRange } from '../../../lib/timeWindow';
import { homeExplainers } from '../explainers';
import { seasonEvents } from '../mocks';
import { TurnoutChart, turnoutModel } from './TurnoutChart';

const threeMonths = windowRange('3m', '2026-09-27');

describe('turnoutModel', () => {
  it('charts turnout per scored Sunday in date order', () => {
    expect(turnoutModel(seasonEvents).rows).toEqual([
      { event_date: '2026-09-06', shooters: 24 },
      { event_date: '2026-09-13', shooters: 13 },
      { event_date: '2026-09-27', shooters: 23 },
    ]);
  });

  it('is the plain bar chart of every Sunday it is given: the frame zooms it inline', () => {
    const early = {
      ...(seasonEvents[0] as (typeof seasonEvents)[number]),
      event_date: '2026-02-01',
    };
    const model = turnoutModel([early, ...seasonEvents]);
    expect(model.rows).toHaveLength(4);
    expect(model.option.dataZoom).toBeUndefined();
  });
});

describe('TurnoutChart', () => {
  it('renders turnout per Sunday in a ChartFrame with Table and CSV controls', () => {
    renderWithProviders(
      <TurnoutChart
        events={seasonEvents}
        range={threeMonths}
        label="Last 3 months"
        explainer={homeExplainers.pulseSheet}
      />,
    );
    const region = screen.getByRole('region', { name: 'Turnout per Sunday' });
    expectChartControls(region);
    expect(
      screen.getByRole('img', { name: 'Turnout per Sunday, last 3 months' }),
    ).toBeInTheDocument();
  });

  it(
    'explains itself and tags a windowed explainer with the time window',
    async () => {
      renderWithProviders(
        <TurnoutChart
          events={seasonEvents}
          range={threeMonths}
          label="Last 3 months"
          explainer={{ ...homeExplainers.pulseSheet, scope: 'windowed' }}
        />,
      );
      const region = screen.getByRole('region', { name: 'Turnout per Sunday' });
      await expectExplainer(region, 'About this chart', { read: true });
      // The scope tag names the URL's window (default: the last 8 weeks) with its dates.
      expect(region).toHaveTextContent('Last 8 weeks · Aug 3 – Sep 27');
      // The subtitle describes the chart; the window and its dates live in the tag alone.
      expect(within(region).getByText('Head count each Sunday')).toBeVisible();
    },
    LAZY_TEST_TIMEOUT,
  );
});

describe('TurnoutChart full data', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  /** Every Sunday on record: nine of them, one per year, so the full set is countable. */
  function everySunday(): URLSearchParams[] {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get('*/api/events', ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        const base = seasonEvents[0] as (typeof seasonEvents)[number];
        return HttpResponse.json(
          Array.from({ length: 9 }, (_, i) => ({ ...base, event_date: `${2018 + i}-01-06` })),
        );
      }),
    );
    return seen;
  }

  // An earlier Sunday than the window, so the inline chart has something to zoom past.
  const early = { ...(seasonEvents[0] as (typeof seasonEvents)[number]), event_date: '2026-02-01' };

  const render = (route = '/') =>
    renderWithProviders(
      <TurnoutChart
        events={[early, ...seasonEvents]}
        range={threeMonths}
        label="Last 3 months"
        explainer={homeExplainers.pulseSheet}
      />,
      { route },
    );

  it(
    'opens on the window inline and on every Sunday in fullscreen, in one request',
    async () => {
      const seen = everySunday();
      const { user } = render();
      const region = screen.getByRole('region', { name: 'Turnout per Sunday' });
      await screen.findByRole('img', { name: /Turnout per Sunday/ }, LAZY_CHART);
      expect(seen).toHaveLength(0);
      const zoomOf = (o: unknown) =>
        (o as { dataZoom?: { startValue?: unknown }[] }).dataZoom ?? [];
      await waitFor(() => expect(zoomOf(chartOptionIn(region))[0]?.startValue).toBeDefined());
      const inlineStart = zoomOf(chartOptionIn(region))[0]?.startValue;
      const dialog = await openFullscreen(user, region, 'Turnout per Sunday');
      expect(await within(dialog).findByText('Every Sunday with scores on record.')).toBeVisible();
      // 2018 to 2026 in ONE request: no year, no dates.
      expect(seen).toHaveLength(1);
      expect([...(seen[0]?.keys() ?? [])]).toEqual([]);
      const zoom = zoomOf(chartOptionIn(dialog));
      expect(zoom).toHaveLength(2);
      // The dialog opens on the first Sunday (index 0 of the category axis), not the window.
      expect(zoom.map((z) => z.startValue)).toEqual([0, 0]);
      expect(inlineStart).not.toBe(0);
      await user.click(screen.getByRole('button', { name: 'Table' }));
      expect(within(dialog).getAllByRole('row')).toHaveLength(10);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'trims the inline table to the window (with a note) while fullscreen lists every year',
    async () => {
      everySunday();
      const { user } = render('/?pulse=table');
      const region = screen.getByRole('region', { name: 'Turnout per Sunday' });
      // The February Sunday is before the window: header + the three Sundays inside it.
      expect(await within(region).findAllByRole('row', {}, LAZY_CHART)).toHaveLength(4);
      expect(
        within(region).getByText(
          'Showing the time window. Open fullscreen or download CSV for every Sunday.',
        ),
      ).toBeVisible();
      const dialog = await openFullscreen(user, region, 'Turnout per Sunday');
      await waitFor(() => expect(within(dialog).getAllByRole('row')).toHaveLength(10), LAZY_CHART);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'exports every year as CSV and passes the round-type filter on',
    async () => {
      const seen = everySunday();
      const csv = captureCsv();
      const { user } = render('/?rt=super_sporting');
      const region = screen.getByRole('region', { name: 'Turnout per Sunday' });
      await screen.findByRole('img', { name: /Turnout per Sunday/ }, LAZY_CHART);
      await user.click(within(region).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toHaveLength(1), LAZY_CHART);
      expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(10);
      expect(seen).toHaveLength(1);
      expect(seen[0]?.getAll('round_type')).toEqual(['super_sporting']);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'reuses the full list the page already loaded instead of fetching it again',
    async () => {
      const seen = everySunday();
      const queryClient = createTestQueryClient();
      const base = seasonEvents[0] as (typeof seasonEvents)[number];
      queryClient.setQueryData(
        ['/api/events', { from: null, to: null, round_type: [] }],
        [base, { ...base, event_date: '2025-01-05' }],
      );
      const { user } = renderWithProviders(
        <TurnoutChart
          events={seasonEvents}
          range={threeMonths}
          label="Last 3 months"
          explainer={homeExplainers.pulseSheet}
        />,
        { queryClient },
      );
      const region = screen.getByRole('region', { name: 'Turnout per Sunday' });
      await screen.findByRole('img', { name: /Turnout per Sunday/ }, LAZY_CHART);
      const dialog = await openFullscreen(user, region, 'Turnout per Sunday');
      expect(await within(dialog).findByText('Every Sunday with scores on record.')).toBeVisible();
      expect(seen).toHaveLength(0);
    },
    LAZY_TEST_TIMEOUT,
  );
});
