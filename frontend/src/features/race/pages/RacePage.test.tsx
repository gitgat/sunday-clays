import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
import { renderRoutes } from '../../../test/render';
import type { LeaderboardHistoryOut } from '../api';
import { historyFixture } from '../mocks';
import { raceIntro } from '../explainers';
import { routes } from '../routes';
import { RacePage } from './RacePage';

function captureRequests(body: LeaderboardHistoryOut = historyFixture): URL[] {
  const seen: URL[] = [];
  server.use(
    http.get('*/api/leaderboards/history', ({ request }) => {
      seen.push(new URL(request.url));
      return HttpResponse.json(body);
    }),
  );
  return seen;
}

/** The Race page on its real route, so its page default window (12 months) applies. */
function renderRace(route: string) {
  return renderRoutes([{ path: '/race', element: <RacePage />, handle: routes[0]?.handle }], {
    route,
  });
}

function standings(): string[] {
  return within(screen.getByRole('list', { name: 'Standings' }))
    .getAllByRole('listitem')
    .map((item) => item.textContent);
}

function lastParams(seen: URL[]): URLSearchParams {
  const url = seen.at(-1);
  if (url === undefined) throw new Error('no /api/leaderboards/history request yet');
  return url.searchParams;
}

function words(text: string): number {
  return text.trim().split(/\s+/).length;
}

describe('RacePage', () => {
  it('opens on 12 months of Sundays, counting points over the last 12 months', async () => {
    const seen = captureRequests();
    const { router } = renderRace('/race?rt=sporting');
    await screen.findByRole('list', { name: 'Standings' });
    const params = lastParams(seen);
    expect(params.get('period')).toBe('rolling_12');
    expect(params.get('metric')).toBe('season_points');
    expect(params.get('top')).toBe('10');
    expect(params.get('from')).toBe('2025-09-28');
    expect(params.get('to')).toBe('2026-09-27');
    expect(params.has('since')).toBe(false);
    expect(params.getAll('round_type')).toEqual(['sporting']);
    expect(router.state.location.search).toBe('?rt=sporting');
    expect(screen.getByRole('button', { name: 'Last 12 months' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('has no dates or period chips of its own: the header window is the only date control', async () => {
    renderRace('/race');
    await screen.findByRole('list', { name: 'Standings' });
    expect(screen.queryByRole('group', { name: 'Period' })).toBeNull();
    expect(screen.queryByLabelText('Start date')).toBeNull();
    expect(screen.queryByLabelText('End date')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Custom dates' })).toBeNull();
  });

  it('opens on the latest frame and scrubs to earlier ones', async () => {
    renderRace('/race');
    await screen.findByRole('list', { name: 'Standings' });
    expect(screen.getByText('Sep 27, 2026', { selector: 'output' })).toBeInTheDocument();
    expect(standings()).toEqual(['1Bee, Bob29', '1Ace, Amy29']);
    fireEvent.change(screen.getByLabelText('Race position'), { target: { value: '0' } });
    expect(screen.getByText('Sep 6, 2026', { selector: 'output' })).toBeInTheDocument();
    expect(standings()).toEqual(['1Ace, Amy11', '2Bee, Bob9']);
  });

  it('toggles between play and pause', async () => {
    const user = userEvent.setup();
    renderRace('/race');
    await user.click(await screen.findByRole('button', { name: 'Play' }));
    expect(screen.getByText('Sep 6, 2026', { selector: 'output' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Pause' }));
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument();
  });

  it('changes the metric through the URL-backed select', async () => {
    const seen = captureRequests();
    const user = userEvent.setup();
    renderRace('/race');
    await screen.findByRole('list', { name: 'Standings' });
    await user.selectOptions(screen.getByLabelText('Metric'), 'Wins');
    await waitFor(() => {
      expect(lastParams(seen).get('metric')).toBe('wins');
    });
  });

  it('offers rating gain in place of the rating ranking', async () => {
    renderRace('/race');
    await screen.findByRole('list', { name: 'Standings' });
    const options = within(screen.getByLabelText('Metric'))
      .getAllByRole('option')
      .map((o) => o.textContent);
    expect(options).toContain('Rating gain');
    expect(options).not.toContain('Rating');
    expect(options).not.toContain('Most improved');
  });

  describe('the header window sets the replayed Sundays', () => {
    it.each([
      ['/race', '2025-09-28', '2026-09-27'],
      ['/race?w=8w', '2026-08-03', '2026-09-27'],
      ['/race?w=3m', '2026-06-28', '2026-09-27'],
      ['/race?w=ytd', '2026-01-01', '2026-09-27'],
      ['/race?w=2025-03-02..2025-06-29', '2025-03-02', '2025-06-29'],
    ])('%s replays %s to %s', async (route, from, to) => {
      const seen = captureRequests();
      renderRace(route);
      await screen.findByRole('list', { name: 'Standings' });
      expect(lastParams(seen).get('from')).toBe(from);
      expect(lastParams(seen).get('to')).toBe(to);
    });

    it('All time replays from the first Sunday', async () => {
      server.use(
        http.get('*/api/meta', () =>
          HttpResponse.json({ first_event_date: '2020-01-05', last_score_date: '2026-09-27' }),
        ),
      );
      const seen = captureRequests();
      renderRace('/race?w=all');
      await screen.findByRole('list', { name: 'Standings' });
      expect(lastParams(seen).get('from')).toBe('2020-01-05');
    });

    it('says which Sundays it is replaying', async () => {
      renderRace('/race?w=8w');
      await screen.findByRole('list', { name: 'Standings' });
      expect(screen.getByText('Replaying Aug 3 – Sep 27 · 3 Sundays')).toBeVisible();
    });

    it('does not ask for All time when the first Sunday is unknown', async () => {
      server.use(
        http.get('*/api/meta', () =>
          HttpResponse.json({ first_event_date: null, last_score_date: '2026-09-27' }),
        ),
      );
      const seen = captureRequests();
      renderRace('/race?w=all');
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(seen).toHaveLength(0);
    });

    it('spells out the years of a Custom window before the latest Sunday is known', async () => {
      server.use(http.get('*/api/meta', () => new Promise(() => undefined)));
      captureRequests();
      renderRace('/race?w=2025-03-02..2025-06-29');
      await screen.findByRole('list', { name: 'Standings' });
      expect(screen.getByText('Replaying Mar 2, 2025 – Jun 29, 2025 · 3 Sundays')).toBeVisible();
    });

    it('does not ask until the latest Sunday is known', async () => {
      server.use(http.get('*/api/meta', () => new Promise(() => undefined)));
      const seen = captureRequests();
      renderRace('/race');
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(seen).toHaveLength(0);
    });
  });

  describe('thin and empty windows', () => {
    it('says only 2 Sundays, naming the period, and widens to All in one tap', async () => {
      captureRequests({ ...historyFixture, frames: historyFixture.frames.slice(1) });
      const user = userEvent.setup();
      const { router } = renderRace('/race?w=8w');
      await screen.findByRole('list', { name: 'Standings' });
      expect(screen.getByText('Only 2 Sundays in the last 8 weeks.')).toBeVisible();
      await user.click(
        within(screen.getByRole('group', { name: 'Widen the window' })).getByRole('button', {
          name: 'All',
        }),
      );
      expect(router.state.location.search).toBe('?w=all');
    });

    it('on the 12M page default, 12M is offered nowhere and writing 8W is explicit', async () => {
      captureRequests({ ...historyFixture, frames: historyFixture.frames.slice(2) });
      renderRace('/race');
      await screen.findByRole('list', { name: 'Standings' });
      expect(screen.getByText('Only 1 Sunday in the last 12 months.')).toBeVisible();
      const widen = screen.getByRole('group', { name: 'Widen the window' });
      expect(within(widen).queryByRole('button', { name: '12M' })).toBeNull();
    });

    it('shows an empty state naming the period, with the widen buttons', async () => {
      captureRequests({ ...historyFixture, frames: [] });
      renderRace('/race?w=3m');
      expect(await screen.findByText('No Sundays with scores in the last 3 months')).toBeVisible();
      expect(screen.getByRole('button', { name: '12M' })).toBeVisible();
      expect(screen.getByRole('button', { name: 'All' })).toBeVisible();
    });

    it('never nudges a window with enough Sundays', async () => {
      const many = Array.from({ length: 5 }, (_, i) => ({
        ...(historyFixture.frames[0] as (typeof historyFixture.frames)[number]),
        event_date: `2026-08-${String(2 + 7 * i).padStart(2, '0')}`,
      }));
      captureRequests({ ...historyFixture, frames: many });
      renderRace('/race');
      await screen.findByRole('list', { name: 'Standings' });
      expect(screen.queryByRole('group', { name: 'Widen the window' })).toBeNull();
    });
  });

  describe('the intro', () => {
    it('is visible on load, before any data, and says what the race and its points are', async () => {
      renderRace('/race');
      const intro = screen.getByRole('region', { name: 'About the race' });
      expect(intro).toBeVisible();
      expect(intro).toHaveTextContent('replays each Sunday');
      expect(intro).toHaveTextContent(
        '1st place earns 10, 2nd 8, 3rd 6, 4th 5, 5th 4, 6th 3, 7th 2 and 8th 1, plus 1 for turning up',
      );
      expect(intro).toHaveTextContent('Ties share a place');
      expect(intro).toHaveTextContent(
        'Last 12 months counts points from the last 52 Sundays. Each Sunday’s points drop off a year later, so there is no reset.',
      );
      await screen.findByRole('list', { name: 'Standings' });
    });

    it.each([
      ['/race', 'no reset'],
      ['/race?period=season', 'Last 8 Sundays counts points from the last 8 Sundays'],
      ['/race?period=ytd', 'It resets every 1 January'],
    ])('follows the chosen points rule at %s', async (route, text) => {
      renderRace(route);
      expect(screen.getByRole('region', { name: 'About the race' })).toHaveTextContent(text);
      await screen.findByRole('list', { name: 'Standings' });
    });

    it('is 60 to 90 words in every mode, in plain neutral wording', () => {
      for (const mode of ['rolling_12', 'season', 'ytd'] as const) {
        const { what, points, mode: modeLine } = raceIntro(mode);
        const text = `${what} ${points} ${modeLine}`;
        expect(words(text), mode).toBeGreaterThanOrEqual(60);
        expect(words(text), mode).toBeLessThanOrEqual(90);
        expect(text, mode).not.toMatch(/\bclass|\bhe\b|\bshe\b|\bhis\b|\bher\b|\bevents?\b/i);
      }
    });
  });

  describe('the points rule', () => {
    it('offers the last 12 months, last 8 Sundays and since Jan 1, in that order', async () => {
      renderRace('/race');
      const group = screen.getByRole('group', { name: 'Points over' });
      expect(
        within(group)
          .getAllByRole('button')
          .map((b) => b.textContent),
      ).toEqual(['Last 12 months', 'Last 8 Sundays', 'Since Jan 1']);
      await screen.findByRole('list', { name: 'Standings' });
    });

    it('labels the points rule on screen, so it never reads like the time window', async () => {
      renderRace('/race');
      expect(screen.getByText('Points over')).toBeVisible();
      await screen.findByRole('list', { name: 'Standings' });
    });

    it('changes only how points are counted, never the replayed Sundays', async () => {
      const seen = captureRequests();
      const user = userEvent.setup();
      const { router } = renderRace('/race?metric=wins');
      await screen.findByRole('list', { name: 'Standings' });
      const group = screen.getByRole('group', { name: 'Points over' });

      await user.click(within(group).getByRole('button', { name: 'Last 8 Sundays' }));
      expect(router.state.location.search).toBe('?metric=wins&period=season');
      await waitFor(() => {
        expect(lastParams(seen).get('period')).toBe('season');
      });
      expect(lastParams(seen).get('from')).toBe('2025-09-28');
      expect(screen.getByRole('region', { name: 'About the race' })).toHaveTextContent(
        'last 8 Sundays',
      );

      await user.click(within(group).getByRole('button', { name: 'Since Jan 1' }));
      expect(router.state.location.search).toBe('?metric=wins&period=ytd');
      await waitFor(() => {
        expect(lastParams(seen).get('period')).toBe('ytd');
      });
      expect(lastParams(seen).get('from')).toBe('2025-09-28');
      expect(screen.getByRole('region', { name: 'About the race' })).toHaveTextContent(
        'resets every 1 January',
      );

      await user.click(within(group).getByRole('button', { name: 'Last 12 months' }));
      expect(router.state.location.search).toBe('?metric=wins');
    });
  });

  describe('old URLs convert once into the window', () => {
    it.each([
      [
        '?since=2025-03-02&until=2025-06-29',
        '?w=2025-03-02..2025-06-29',
        '2025-03-02',
        '2025-06-29',
      ],
      ['?since=2025-03-02', '?w=2025-03-02..2026-09-27', '2025-03-02', '2026-09-27'],
      ['?since=2025-06-29&until=2025-03-02', '', '2025-09-28', '2026-09-27'],
      ['?until=2025-06-29', '', '2025-09-28', '2026-09-27'],
      ['?period=ytd', '?period=ytd', '2025-09-28', '2026-09-27'],
      ['?period=season', '?period=season', '2025-09-28', '2026-09-27'],
      [
        '?since=2025-03-02&until=2025-06-29&year=2024&period=all_time',
        '?year=2024&period=all_time&w=2025-03-02..2025-06-29',
        '2025-03-02',
        '2025-06-29',
      ],
    ])('%s becomes "%s"', async (old, search, from, to) => {
      const seen = captureRequests();
      const { router } = renderRace(`/race${old}`);
      await screen.findByRole('list', { name: 'Standings' });
      expect(router.state.location.search).toBe(search);
      expect(lastParams(seen).get('from')).toBe(from);
      expect(lastParams(seen).get('to')).toBe(to);
      expect(lastParams(seen).has('since')).toBe(false);
      // The first request is already the converted one: the old URL never replays the wrong Sundays.
      expect(new Set(seen.map((url) => url.search)).size).toBe(1);
    });

    it('an explicit w beats old dates, which are still removed', async () => {
      const { router } = renderRace('/race?w=6m&since=2025-03-02&until=2025-06-29');
      await screen.findByRole('list', { name: 'Standings' });
      expect(router.state.location.search).toBe('?w=6m');
    });

    it.each(['rating', 'most_improved'])('metric=%s becomes rating_gain', async (metric) => {
      const seen = captureRequests();
      const { router } = renderRace(`/race?metric=${metric}`);
      await screen.findByRole('list', { name: 'Standings' });
      expect(router.state.location.search).toBe('?metric=rating_gain');
      expect(lastParams(seen).get('metric')).toBe('rating_gain');
    });

    it('waits for the latest Sunday to fill in a missing end date', async () => {
      server.use(http.get('*/api/meta', () => new Promise(() => undefined)));
      const seen = captureRequests();
      const { router } = renderRace('/race?since=2025-03-02');
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(seen).toHaveLength(0);
      expect(router.state.location.search).toBe('?since=2025-03-02');
    });
  });

  it('shows an error state when the API fails', async () => {
    server.use(
      http.get('*/api/leaderboards/history', () => new HttpResponse(null, { status: 500 })),
    );
    renderRace('/race');
    expect(await screen.findByText('Race unavailable')).toBeInTheDocument();
  });

  it('every data chart exposes Table and CSV controls', async () => {
    renderRace('/race');
    await screen.findByRole('list', { name: 'Standings' });
    for (const title of ['Points', 'Rank over time']) {
      expectChartControls(screen.getByRole('region', { name: title }));
    }
  });

  it('explains both charts, tagged with the time window, with the points-rule line', async () => {
    renderRace('/race?w=6m&period=season');
    await screen.findByRole('list', { name: 'Standings' });
    for (const title of ['Points', 'Rank over time']) {
      const region = screen.getByRole('region', { name: title });
      await expectExplainer(region, 'About this chart', { read: true });
      const user = userEvent.setup();
      await user.click(within(region).getByRole('button', { name: 'About this chart' }));
      expect(within(region).getByText(/^Last 6 months( · .+)?$/)).toBeVisible();
      expect(within(region).queryByText('All time')).toBeNull();
      expect(within(region).getByText(/last 8 Sundays \(56 days\)/)).toBeVisible();
    }
  });

  describe('full data in fullscreen and CSV', () => {
    afterEach(() => vi.restoreAllMocks());

    const DATES = ['2026-09-06', '2026-09-13', '2026-09-27'];
    const RANKED = 30;
    /** Three Sundays with 30 ranked shooters each; the API cuts every frame to `top`. */
    function serveRanked(seen: URL[]) {
      server.use(
        http.get('*/api/leaderboards/history', ({ request }) => {
          const url = new URL(request.url);
          seen.push(url);
          const top = Number(url.searchParams.get('top'));
          return HttpResponse.json({
            ...historyFixture,
            frames: DATES.map((event_date) => ({
              event_date,
              rows: Array.from({ length: Math.min(top, RANKED) }, (_, i) => ({
                shooter_id: 100 + i,
                display_name: `Shooter ${String(i + 1).padStart(2, '0')}`,
                status: 'member' as const,
                value: 100 - i,
                rank: i + 1,
              })),
            })),
          });
        }),
      );
    }
    const rowCount = (el: HTMLElement) => within(el).getAllByRole('row').length;
    const topOf = (seen: URL[], top: number) =>
      seen.filter((u) => u.searchParams.get('top') === String(top));

    it('race bars: the fullscreen table and CSV list everyone ranked that Sunday', async () => {
      const seen: URL[] = [];
      serveRanked(seen);
      const csv = captureCsv();
      const { user } = renderRace('/race?rt=sporting&race-bars=table');
      const card = await screen.findByRole('region', { name: 'Points' });
      expect(rowCount(card)).toBe(1 + 10);
      expect(topOf(seen, 50)).toHaveLength(0);
      const dialog = await openFullscreen(user, card, 'Points');
      expect(await within(dialog).findByText('The top 50 ranked that Sunday.')).toBeInTheDocument();
      expect(rowCount(dialog)).toBe(1 + RANKED);
      const full = topOf(seen, 50);
      expect(full).toHaveLength(1);
      // The same query as the page's own, but for the top 50.
      const own = topOf(seen, 10)[0];
      for (const key of ['period', 'metric', 'from', 'to']) {
        expect(full[0]?.searchParams.get(key), key).toBe(own?.searchParams.get(key));
      }
      expect(full[0]?.searchParams.getAll('round_type')).toEqual(['sporting']);
      await user.click(within(card).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toEqual(['race-season_points-2026-09-27.csv']));
      expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(1 + RANKED);
      expect(topOf(seen, 50)).toHaveLength(1);
    });

    it('rank over time: the table and CSV hold every ranked shooter on every Sunday, and both charts share one fetch', async () => {
      const seen: URL[] = [];
      serveRanked(seen);
      const csv = captureCsv();
      const { user } = renderRace('/race?race-bump=table');
      const card = await screen.findByRole('region', { name: 'Rank over time' });
      expect(rowCount(card)).toBe(1 + 10 * DATES.length);
      const dialog = await openFullscreen(user, card, 'Rank over time');
      expect(
        await within(dialog).findByText('The top 50 ranked on every Sunday.'),
      ).toBeInTheDocument();
      expect(rowCount(dialog)).toBe(1 + RANKED * DATES.length);
      await user.click(within(card).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toEqual(['race-ranks-season_points.csv']));
      expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(1 + RANKED * DATES.length);
      // The bars chart's fullscreen finds the same top-500 answer already cached.
      await user.click(within(dialog).getByRole('button', { name: 'Close' }));
      await openFullscreen(user, screen.getByRole('region', { name: 'Points' }), 'Points');
      await screen.findByText('The top 50 ranked that Sunday.');
      expect(topOf(seen, 50)).toHaveLength(1);
    });

    it(
      'draws every ranked shooter up to 50 in both fullscreens, the race sheet tall enough for each bar',
      async () => {
        serveRanked([]);
        const { user } = renderRace('/race');
        const bars = await screen.findByRole('region', { name: 'Points' });
        await within(bars).findByRole('img', { name: /race bar chart/ }, LAZY_CHART);
        // The axis holds every ranked shooter; `max` is the last bar drawn (0-based).
        const drawn = (o: ReturnType<typeof chartOptionIn>) =>
          ((o.yAxis as { max: number }[])[0] as { max: number }).max + 1;
        expect(drawn(chartOptionIn(bars, /race bar chart/))).toBe(10);
        const dialog = await openFullscreen(user, bars, 'Points');
        await within(dialog).findByRole('img', { name: /race bar chart/ }, LAZY_CHART);
        await waitFor(() => expect(drawn(chartOptionIn(dialog, /race bar chart/))).toBe(RANKED));
        expect(within(dialog).getByRole('img', { name: /race bar chart/ })).toHaveStyle({
          height: `${80 + 28 * RANKED}px`,
        });
        await user.click(within(dialog).getByRole('button', { name: 'Close' }));
        const bump = screen.getByRole('region', { name: 'Rank over time' });
        await within(bump).findByRole('img', { name: /rank bump chart/ }, LAZY_CHART);
        expect(chartOptionIn(bump, /rank bump chart/).series).toHaveLength(10);
        const bumpDialog = await openFullscreen(user, bump, 'Rank over time');
        await within(bumpDialog).findByRole('img', { name: /rank bump chart/ }, LAZY_CHART);
        await waitFor(() =>
          expect(chartOptionIn(bumpDialog, /rank bump chart/).series).toHaveLength(RANKED),
        );
      },
      LAZY_TEST_TIMEOUT,
    );

    it('keeps the card as it is when the full answer has no frame for that Sunday', async () => {
      server.use(
        http.get('*/api/leaderboards/history', ({ request }) =>
          HttpResponse.json(
            new URL(request.url).searchParams.get('top') === '50'
              ? { ...historyFixture, frames: [] }
              : historyFixture,
          ),
        ),
      );
      const { user } = renderRace('/race?race-bars=table');
      const card = await screen.findByRole('region', { name: 'Points' });
      const inline = rowCount(card);
      const dialog = await openFullscreen(user, card, 'Points');
      await waitFor(() => expect(within(dialog).queryByRole('status')).not.toBeInTheDocument());
      expect(rowCount(dialog)).toBe(inline);
      expect(within(dialog).queryByText(/^The top 50 ranked/)).not.toBeInTheDocument();
    });

    it('keeps the card when the full fetch fails', async () => {
      const seen: URL[] = [];
      serveRanked(seen);
      server.use(
        http.get('*/api/leaderboards/history', ({ request }) => {
          const url = new URL(request.url);
          if (url.searchParams.get('top') === '50') return HttpResponse.error();
          seen.push(url);
          return HttpResponse.json(historyFixture);
        }),
      );
      const { user } = renderRace('/race');
      const card = await screen.findByRole('region', { name: 'Points' });
      const dialog = await openFullscreen(user, card, 'Points');
      expect(await within(dialog).findByRole('alert')).toHaveTextContent(
        "Couldn't load the full data.",
      );
    });
  });
});
