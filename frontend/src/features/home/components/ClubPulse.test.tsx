import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeAll, describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { expectChartControls, expectExplainer } from '../../../test/charts';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { renderWithProviders } from '../../../test/render';
import type { EventSummary } from '../api';
import { homeMeta, seasonEvents } from '../mocks';
import { ClubPulse, pulseStats } from './ClubPulse';

// ClubPulse loads its chart lazily. Warm that module (and ECharts) once, so findBy*'s 1 s
// budget never covers a cold import, and every test that loads the season waits for the chart:
// a lazy chart resolving after a test ends would log React's act() warning.
beforeAll(async () => {
  await import('./TurnoutChart');
});

describe('pulseStats', () => {
  it('counts scored Sundays, averages turnout (head count, else shooters) and finds the highest score', () => {
    expect(pulseStats(seasonEvents)).toEqual({
      held: 3,
      scored: 3,
      avgTurnout: 20,
      seasonHigh: 49,
    });
  });

  it('counts only results-complete Sundays as full-results (C7), and every scored Sunday elsewhere', () => {
    const week = seasonEvents[0] as EventSummary;
    const incomplete: EventSummary = {
      ...week,
      event_date: '2026-09-20',
      results_complete: false,
      head_count: 27,
      n_shooters: 7,
      top_score: 50,
    };
    expect(pulseStats([...seasonEvents, incomplete])).toEqual({
      held: 3,
      scored: 4,
      avgTurnout: 21.8,
      seasonHigh: 50,
    });
  });

  it('leaves a scored Sunday without a top score out of the highest score', () => {
    const week = seasonEvents[0] as EventSummary;
    expect(pulseStats([{ ...week, top_score: null }])).toEqual({
      held: 1,
      scored: 1,
      avgTurnout: 13,
      seasonHigh: null,
    });
  });

  it('has no averages without scored events', () => {
    expect(pulseStats(seasonEvents.slice(3))).toEqual({
      held: 0,
      scored: 0,
      avgTurnout: null,
      seasonHigh: null,
    });
  });
});

const events = (list: EventSummary[]) => http.get('*/api/events', () => HttpResponse.json(list));
const metaHandler = (over: Partial<typeof homeMeta> = {}) =>
  http.get('*/api/meta', () => HttpResponse.json({ ...homeMeta, ...over }));
/** The stat tile (its whole box) that carries `label`. */
const statOf = (within_: HTMLElement, label: string): HTMLElement | null =>
  within(within_).getByText(label).closest('.flex-col');
const chart = () => screen.findByRole('region', { name: 'Turnout per Sunday' }, LAZY_CHART);

describe('ClubPulse', () => {
  it(
    'shows the stats and the turnout chart for the time window, in one request for its dates',
    async () => {
      const seen: URLSearchParams[] = [];
      server.use(
        metaHandler(),
        http.get('*/api/events', ({ request }) => {
          seen.push(new URL(request.url).searchParams);
          return HttpResponse.json(seasonEvents);
        }),
      );
      renderWithProviders(<ClubPulse />);
      await chart();
      const pulse = screen.getByRole('region', { name: 'Club pulse' });
      // The default window: the last 8 weeks, counted back from the latest scored Sunday.
      expect(within(pulse).getAllByText('Last 8 weeks · Aug 3 – Sep 27').length).toBeGreaterThan(0);
      expect(within(pulse).getByText('20')).toBeInTheDocument();
      expect(within(pulse).getByText('49')).toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(1);
      expect(seen).toHaveLength(1);
      expect(seen[0]?.get('from')).toBe('2026-08-03');
      expect(seen[0]?.get('to')).toBe('2026-09-27');
      expect(seen[0]?.has('year')).toBe(false);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'follows the time window: stats count only Sundays inside it',
    async () => {
      const week = seasonEvents[0] as EventSummary;
      const march = { ...week, event_date: '2026-03-01', top_score: 50, head_count: 40 };
      server.use(metaHandler(), events([...seasonEvents, march]));

      const { unmount } = renderWithProviders(<ClubPulse />);
      await chart();
      let pulse = screen.getByRole('region', { name: 'Club pulse' });
      expect(statOf(pulse, 'Highest score')).toHaveTextContent('49');
      expect(statOf(pulse, 'Sundays with full results')).toHaveTextContent('3');
      unmount();

      renderWithProviders(<ClubPulse />, { route: '/?w=ytd' });
      await chart();
      pulse = screen.getByRole('region', { name: 'Club pulse' });
      expect(
        within(pulse).getAllByText('This year to date · Jan 1 – Sep 27').length,
      ).toBeGreaterThan(0);
      expect(statOf(pulse, 'Highest score')).toHaveTextContent('50');
      expect(statOf(pulse, 'Sundays with full results')).toHaveTextContent('4');
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'asks once however many years the window spans, and leaves the start open for all time',
    async () => {
      const seen: URLSearchParams[] = [];
      server.use(
        metaHandler({ last_score_date: '2026-02-01', first_event_date: '2024-05-05' }),
        http.get('*/api/events', ({ request }) => {
          seen.push(new URL(request.url).searchParams);
          const week = seasonEvents[0] as EventSummary;
          return HttpResponse.json([{ ...week, event_date: '2026-01-25' }]);
        }),
      );
      const { unmount } = renderWithProviders(<ClubPulse />);
      await chart();
      // 8 weeks back from 2026-02-01 crosses New Year: still one request.
      expect(seen).toHaveLength(1);
      expect(seen[0]?.get('from')).toBe('2025-12-08');
      unmount();
      seen.length = 0;
      renderWithProviders(<ClubPulse />, { route: '/?w=all' });
      await chart();
      // All time spans three calendar years: one request, no start date, no year.
      expect(seen).toHaveLength(1);
      expect(seen[0]?.has('from')).toBe(false);
      expect(seen[0]?.get('to')).toBe('2026-02-01');
      expect(seen[0]?.has('year')).toBe(false);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'renders the turnout chart as its own card, not inside the pulse card',
    async () => {
      server.use(metaHandler(), events(seasonEvents));
      renderWithProviders(<ClubPulse />);
      const turnout = await chart();
      const pulse = screen.getByRole('region', { name: 'Club pulse' });
      // A card inside a card costs the chart header 32px on a phone, truncating its title.
      expect(pulse).not.toContainElement(turnout);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'explains each stat and the chart',
    async () => {
      server.use(metaHandler(), events(seasonEvents));
      renderWithProviders(<ClubPulse />);
      const turnout = await chart();
      const pulse = screen.getByRole('region', { name: 'Club pulse' });
      for (const stat of ['Sundays with full results', 'Avg turnout', 'Highest score']) {
        await expectExplainer(pulse, `About ${stat}`);
      }
      await expectExplainer(turnout, 'About this chart', { read: true });
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'appends the global round-type filter to the requests',
    async () => {
      const seen: string[][] = [];
      server.use(
        metaHandler(),
        http.get('*/api/events', ({ request }) => {
          seen.push(new URL(request.url).searchParams.getAll('round_type'));
          return HttpResponse.json(seasonEvents);
        }),
      );
      renderWithProviders(<ClubPulse />, { route: '/?rt=super_sporting' });
      await chart();
      expect(seen.at(-1)).toEqual(['super_sporting']);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'shows a dash, never "null", when no scored Sunday has a top score',
    async () => {
      server.use(metaHandler(), events(seasonEvents.map((e) => ({ ...e, top_score: null }))));
      renderWithProviders(<ClubPulse />);
      await chart();
      const pulse = screen.getByRole('region', { name: 'Club pulse' });
      expect(within(pulse).queryByText(/null/)).not.toBeInTheDocument();
      expect(statOf(pulse, 'Highest score')).toHaveTextContent('—');
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'counts an incomplete scored Sunday in turnout but not as full results',
    async () => {
      const week = seasonEvents[0] as EventSummary;
      server.use(
        metaHandler(),
        events([{ ...week, event_date: '2026-09-20', results_complete: false, head_count: 27 }]),
      );
      renderWithProviders(<ClubPulse />);
      await chart();
      const pulse = screen.getByRole('region', { name: 'Club pulse' });
      expect(statOf(pulse, 'Sundays with full results')).toHaveTextContent('0');
      expect(statOf(pulse, 'Avg turnout')).toHaveTextContent('27');
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'says so when the time window has no scored Sundays, and keeps the chart card reachable',
    async () => {
      server.use(metaHandler(), events(seasonEvents.slice(3)));
      const { user, router } = renderWithProviders(<ClubPulse />);
      // One message, in the turnout card: no second "no Sundays" line in a pulse card above it.
      const region = await screen.findByRole('region', { name: 'Turnout per Sunday' }, LAZY_CHART);
      expect(screen.queryByRole('region', { name: 'Club pulse' })).toBeNull();
      expect(screen.queryByText('No Sundays with scores in the last 8 weeks.')).toBeNull();
      expectChartControls(region);
      expect(within(region).getByRole('button', { name: 'Fullscreen' })).toBeVisible();
      expect(
        within(region).getByText('No scored Sundays in the last 8 weeks (Aug 3 – Sep 27).'),
      ).toBeVisible();
      // 12M and All, one tap each.
      expect(within(region).getByRole('button', { name: 'Show the last 12 months' })).toBeVisible();
      await user.click(within(region).getByRole('button', { name: 'Show all time' }));
      expect(router.state.location.search).toBe('?w=all');
    },
    LAZY_TEST_TIMEOUT,
  );

  it('says no scored Sundays yet before any import', async () => {
    server.use(metaHandler({ last_score_date: null, last_event_date: null }));
    renderWithProviders(<ClubPulse />);
    expect(await screen.findByText('No scored Sundays yet')).toBeInTheDocument();
  });

  it('shows a load failure', async () => {
    server.use(
      metaHandler(),
      http.get('*/api/events', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<ClubPulse />);
    expect(await screen.findByText("Couldn't load these Sundays")).toBeInTheDocument();
  });

  it('falls back to the empty state when meta fails', async () => {
    server.use(
      http.get('*/api/meta', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<ClubPulse />);
    expect(await screen.findByText('No scored Sundays yet')).toBeInTheDocument();
  });
});
