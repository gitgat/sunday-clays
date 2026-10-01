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

/** The Sheet's 8 weeks up to the issue's Sunday. */
const RANGE = { from: '2026-08-03', to: '2026-09-27' };

describe('ClubPulse', () => {
  it(
    'shows the stats and the turnout chart for the 8 weeks, in one request for its dates',
    async () => {
      const seen: URLSearchParams[] = [];
      server.use(
        metaHandler(),
        http.get('*/api/events', ({ request }) => {
          seen.push(new URL(request.url).searchParams);
          return HttpResponse.json(seasonEvents);
        }),
      );
      const { user } = renderWithProviders(<ClubPulse range={RANGE} />, { route: '/?w=all' });
      const region = await chart();
      const pulse = screen.getByRole('region', { name: 'Club pulse' });
      // The header window (here All time) does not apply: the 8 weeks up to the issue do.
      expect(
        within(pulse).getByText('8 weeks to Sep 27, 2026 · not affected by the time filter'),
      ).toBeInTheDocument();
      expect(within(pulse).getByText('20')).toBeInTheDocument();
      expect(within(pulse).getByText('49')).toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(1);
      expect(seen.map((q) => [q.get('from'), q.get('to'), q.has('year')])).toEqual([
        ['2026-08-03', '2026-09-27', false],
      ]);
      await user.click(within(region).getByRole('button', { name: 'About this chart' }));
      expect(within(region).getByText(/the Sheet always shows the 8 weeks/)).toBeInTheDocument();
      expect(within(region).queryByText(/Last 8 weeks|All time/)).toBeNull();
      await user.click(within(pulse).getByRole('button', { name: 'About Highest score' }));
      expect(within(pulse).getByText(/in those 8 weeks/)).toBeInTheDocument();
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'counts only Sundays inside its range',
    async () => {
      const week = seasonEvents[0] as EventSummary;
      const march = { ...week, event_date: '2026-03-01', top_score: 50, head_count: 40 };
      server.use(metaHandler(), events([...seasonEvents, march]));
      renderWithProviders(<ClubPulse range={RANGE} />);
      await chart();
      const pulse = screen.getByRole('region', { name: 'Club pulse' });
      expect(statOf(pulse, 'Highest score')).toHaveTextContent('49');
      expect(statOf(pulse, 'Sundays with full results')).toHaveTextContent('3');
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'renders the turnout chart as its own card, not inside the pulse card',
    async () => {
      server.use(metaHandler(), events(seasonEvents));
      renderWithProviders(<ClubPulse range={RANGE} />);
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
      renderWithProviders(<ClubPulse range={RANGE} />);
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
      renderWithProviders(<ClubPulse range={RANGE} />, { route: '/?rt=super_sporting' });
      await chart();
      expect(seen.at(-1)).toEqual(['super_sporting']);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'shows a dash, never "null", when no scored Sunday has a top score',
    async () => {
      server.use(metaHandler(), events(seasonEvents.map((e) => ({ ...e, top_score: null }))));
      renderWithProviders(<ClubPulse range={RANGE} />);
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
      renderWithProviders(<ClubPulse range={RANGE} />);
      await chart();
      const pulse = screen.getByRole('region', { name: 'Club pulse' });
      expect(statOf(pulse, 'Sundays with full results')).toHaveTextContent('0');
      expect(statOf(pulse, 'Avg turnout')).toHaveTextContent('27');
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'says so when the 8 weeks have no scored Sundays',
    async () => {
      server.use(metaHandler(), events(seasonEvents.slice(3)));
      renderWithProviders(<ClubPulse range={RANGE} />);
      expect(await screen.findByText('No scored Sundays in these 8 weeks')).toBeVisible();
      const pulse = screen.getByRole('region', { name: 'Club pulse' });
      expect(
        within(pulse).getByText('8 weeks to Sep 27, 2026 · not affected by the time filter'),
      ).toBeVisible();
      // Home kept the chart: its Table, CSV and Fullscreen still reach every Sunday on record.
      const chartRegion = await chart();
      expectChartControls(chartRegion);
      expect(within(chartRegion).getByRole('button', { name: 'Fullscreen' })).toBeInTheDocument();
      expect(
        within(chartRegion).getByRole('button', { name: 'About this chart' }),
      ).toBeInTheDocument();
      expect(within(chartRegion).getByText('No scored Sundays in these 8 weeks.')).toBeVisible();
      // The 8 weeks are fixed: nothing to widen.
      expect(screen.queryByRole('button', { name: 'Show all time' })).toBeNull();
      expect(screen.queryByRole('button', { name: 'Show the last 12 months' })).toBeNull();
    },
    LAZY_TEST_TIMEOUT,
  );

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
    renderWithProviders(<ClubPulse range={RANGE} />);
    expect(await screen.findByText("Couldn't load these Sundays")).toBeInTheDocument();
  });
});
