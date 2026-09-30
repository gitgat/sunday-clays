import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { chartOptionIn, captureCsv, openFullscreen } from '../../../test/charts';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { seasonEvents } from '../../home/mocks';
import { clubAttendance, clubTrends as baseTrends } from '../mocks';
import { AttendanceChart, DifficultyChart, ScoreTrendChart } from './ClubCharts';
import { TurnoutWeatherCard } from './TurnoutWeatherCard';

beforeAll(async () => {
  await Promise.all([import('./ClubCharts'), import('./TurnoutWeatherCard')]);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// An earlier Sunday than the time window, so the inline zoom differs from the whole axis.
const clubTrends = {
  ...baseTrends,
  events: [
    { ...(baseTrends.events[0] as (typeof baseTrends.events)[number]), event_date: '2025-01-05' },
    ...baseTrends.events,
  ],
};

const zoomOf = (option: unknown) =>
  (option as { dataZoom?: { startValue?: unknown }[] }).dataZoom ?? [];

// Fullscreen shows every Sunday: the inline chart opens on the time window, the sheet does not.
describe.each([
  [
    'Attendance per Sunday',
    <AttendanceChart key="a" />,
    clubAttendance.length,
    new Date(2018, 11, 30).getTime(),
  ],
  [
    'Median and top score',
    <ScoreTrendChart key="s" />,
    clubTrends.events.length,
    new Date(2025, 0, 5).getTime(),
  ],
  [
    'Difficulty by Sunday',
    <DifficultyChart key="d" />,
    clubTrends.events.length,
    new Date(2025, 0, 5).getTime(),
  ],
])('%s', (title, chart, count, first) => {
  it(
    'opens zoomed inline, opens on every Sunday in fullscreen and exports every row',
    async () => {
      server.use(
        http.get('*/api/club/attendance', () => HttpResponse.json(clubAttendance)),
        http.get('*/api/club/trends', () => HttpResponse.json(clubTrends)),
      );
      const csv = captureCsv();
      const { user } = renderWithProviders(chart, { route: '/club' });
      await screen.findByRole('img', { name: `${title} chart` }, LAZY_CHART);
      const region = screen.getByRole('region', { name: title });
      await waitFor(() => expect(zoomOf(chartOptionIn(region))[0]?.startValue).toBeDefined());
      const inlineStart = zoomOf(chartOptionIn(region))[0]?.startValue;
      await user.click(within(region).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toHaveLength(1));
      expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(count + 1);
      const dialog = await openFullscreen(user, region, title);
      await within(dialog).findByRole('img', { name: `${title} chart` }, LAZY_CHART);
      // getOption reports the resolved range: fullscreen starts on the first Sunday, not the window.
      const zoom = zoomOf(chartOptionIn(dialog));
      expect(zoom).toHaveLength(2);
      expect(zoom.map((z) => z.startValue)).toEqual([first, first]);
      expect(first).not.toEqual(inlineStart);
      await user.click(screen.getByRole('button', { name: 'Table' }));
      expect(within(dialog).getAllByRole('row')).toHaveLength(count + 1);
    },
    LAZY_TEST_TIMEOUT,
  );
});

describe('Turnout vs weather', () => {
  it(
    'asks for every Sunday on record in fullscreen and for the CSV',
    async () => {
      const specs: {
        limit: number;
        filters: { date_from: string | null; date_to: string | null };
      }[] = [];
      server.use(
        http.post('*/api/explore', async ({ request }) => {
          const spec = (await request.json()) as (typeof specs)[number];
          specs.push(spec);
          return HttpResponse.json({
            columns: [
              { key: 'condition', label: 'Condition', type: 'string' },
              { key: 'value', label: 'Attendance (avg)', type: 'number' },
            ],
            rows:
              spec.limit === 5000
                ? [
                    { condition: 'clear', value: 24.1 },
                    { condition: 'rain', value: 17.5 },
                    { condition: 'windy', value: 19 },
                  ]
                : [{ condition: 'clear', value: 24.1 }],
            n_rounds: 0,
            truncated: false,
          });
        }),
      );
      const csv = captureCsv();
      const { user } = renderWithProviders(<TurnoutWeatherCard />, { route: '/club' });
      await screen.findByRole('img', { name: 'Turnout vs weather' }, LAZY_CHART);
      const region = screen.getByRole('region', { name: 'Turnout vs weather' });
      // On the page: the time window's dates.
      expect(specs).toHaveLength(1);
      expect(specs[0]?.filters.date_from).not.toBeNull();
      expect(specs[0]?.limit).toBe(500);
      await user.click(within(region).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toHaveLength(1));
      const full = specs.at(-1);
      expect(full?.limit).toBe(5000);
      expect(full?.filters.date_from).toBeNull();
      expect(full?.filters.date_to).toBeNull();
      expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(4);
      const dialog = await openFullscreen(user, region, 'Turnout vs weather');
      await user.click(screen.getByRole('button', { name: 'Table' }));
      await waitFor(() => expect(within(dialog).getAllByRole('row')).toHaveLength(4));
    },
    LAZY_TEST_TIMEOUT,
  );
});

describe('Turnout vs weather, thin window', () => {
  it(
    'says how few Sundays the window holds and widens it in one tap',
    async () => {
      const { user, router } = renderWithProviders(<TurnoutWeatherCard />, { route: '/club' });
      expect(
        await screen.findByText(
          'Only 4 Sundays in the last 8 weeks. Weather patterns need more.',
          {},
          LAZY_CHART,
        ),
      ).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Show all time' }));
      expect(router.state.location.search).toBe('?w=all');
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'says nothing rather than "No Sundays" when the events request fails',
    async () => {
      server.use(http.get('*/api/events', () => HttpResponse.json({}, { status: 500 })));
      renderWithProviders(<TurnoutWeatherCard />, { route: '/club' });
      await screen.findByRole('img', { name: 'Turnout vs weather' }, LAZY_CHART);
      expect(screen.queryByText(/No Sundays/)).toBeNull();
      expect(screen.queryByText(/Weather patterns need more/)).toBeNull();
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'stays quiet once the window has 12 Sundays or more',
    async () => {
      const base = seasonEvents[0] as (typeof seasonEvents)[number];
      server.use(
        http.get('*/api/events', () =>
          HttpResponse.json(
            Array.from({ length: 12 }, (_, i) => ({
              ...base,
              event_date: `2026-09-${String(i + 1).padStart(2, '0')}`,
            })),
          ),
        ),
      );
      renderWithProviders(<TurnoutWeatherCard />, { route: '/club' });
      await screen.findByRole('img', { name: 'Turnout vs weather' }, LAZY_CHART);
      expect(screen.queryByText(/Weather patterns need more/)).toBeNull();
    },
    LAZY_TEST_TIMEOUT,
  );
});
