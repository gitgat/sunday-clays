import { screen, waitFor, within } from '@testing-library/react';
import { getInstanceByDom } from 'echarts/core';
import { http, HttpResponse } from 'msw';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  captureCsv,
  expectChartControls,
  expectExplainer,
  openFullscreen,
} from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { RecordsOut } from '../api';
import { recordsFixture } from '../mocks';
import { RecordsPage } from './RecordsPage';

const LAZY = { timeout: 10_000 };

afterEach(() => vi.restoreAllMocks());

describe('RecordsPage', () => {
  it('shows every record section', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records' });
    expect(await screen.findByRole('heading', { name: 'Highest scores' })).toBeInTheDocument();
    for (const title of [
      'Perfect 50s',
      'Biggest day vs the field',
      'Biggest jump from one Sunday to the next',
      'Most Sundays shot',
      'Longest streaks',
      'Highest rating in these dates',
    ]) {
      expect(screen.getByRole('region', { name: title })).toBeInTheDocument();
    }
  });

  it('ranks highest scores with shared ranks and links shooter and event', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records' });
    const table = await screen.findByRole('table', { name: 'Highest scores' });
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((row) => within(row).getAllByRole('cell')[0]?.textContent)).toEqual([
      '1',
      '1',
      '3',
    ]);
    const first = rows[0] ?? table;
    expect(within(first).getByRole('link', { name: 'Ace, Amy' })).toHaveAttribute(
      'href',
      '/shooters/7',
    );
    expect(within(first).getByRole('link', { name: 'Jan 17, 2021' })).toHaveAttribute(
      'href',
      '/events/2021-01-17',
    );
  });

  it('keeps the round-type filter on shooter and event links', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records?rt=super_sporting' });
    const table = await screen.findByRole('table', { name: 'Highest scores' });
    expect(within(table).getAllByRole('link', { name: 'Ace, Amy' })[0]).toHaveAttribute(
      'href',
      '/shooters/7?rt=super_sporting',
    );
    expect(within(table).getByRole('link', { name: 'Jan 17, 2021' })).toHaveAttribute(
      'href',
      '/events/2021-01-17?rt=super_sporting',
    );
    const perfect = screen.getByRole('region', { name: 'Perfect 50s' });
    expect(within(perfect).getByRole('link', { name: 'Bee, Bob' })).toHaveAttribute(
      'href',
      '/shooters/3?rt=super_sporting',
    );
  });

  it('lists every perfect round and formats the other records', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records' });
    const perfect = await screen.findByRole('region', { name: 'Perfect 50s' });
    expect(within(perfect).getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByText('+18.0')).toBeInTheDocument();
    expect(screen.getByText('11 → 41 (+30)')).toBeInTheDocument();
    expect(screen.getByText('47.3')).toBeInTheDocument();
  });

  it('keeps two same-day rounds by one shooter as separate rows', async () => {
    const twice = {
      rank: 1,
      shooter_id: 7,
      display_name: 'Ace, Amy',
      event_date: '2026-08-30',
      value: 40,
    };
    server.use(
      http.get('*/api/records', () =>
        HttpResponse.json({ ...recordsFixture, highest_scores: [twice, twice] }),
      ),
    );
    renderWithProviders(<RecordsPage />, { route: '/records' });
    const table = await screen.findByRole('table', { name: 'Highest scores' });
    expect(within(table).getAllByRole('row')).toHaveLength(3);
  });

  it('forwards the global round-type filter', async () => {
    const seen: URL[] = [];
    server.use(
      http.get('*/api/records', ({ request }) => {
        seen.push(new URL(request.url));
        return HttpResponse.json(recordsFixture);
      }),
    );
    renderWithProviders(<RecordsPage />, { route: '/records?rt=super_sporting' });
    await screen.findByRole('table', { name: 'Highest scores' });
    expect(seen.at(-1)?.searchParams.getAll('round_type')).toEqual(['super_sporting']);
  });

  it('sends no round_type without a filter', async () => {
    const seen: URL[] = [];
    server.use(
      http.get('*/api/records', ({ request }) => {
        seen.push(new URL(request.url));
        return HttpResponse.json(recordsFixture);
      }),
    );
    renderWithProviders(<RecordsPage />, { route: '/records' });
    await screen.findByRole('table', { name: 'Highest scores' });
    expect(seen.at(-1)?.searchParams.has('round_type')).toBe(false);
  });

  it('says None yet for empty record lists', async () => {
    server.use(
      http.get('*/api/records', () =>
        HttpResponse.json({
          ...recordsFixture,
          perfect_rounds: [],
          most_events: [],
          biggest_jumps: [],
          highest_ratings: [],
          biggest_adjusted: [],
          longest_streaks: [],
        }),
      ),
    );
    renderWithProviders(<RecordsPage />, { route: '/records' });
    const perfect = await screen.findByRole('region', { name: 'Perfect 50s' });
    expect(within(perfect).getByText('None yet')).toBeInTheDocument();
    expect(screen.getAllByText('None yet')).toHaveLength(6);
  });

  it('shows a loading state, then an error state when the API fails', async () => {
    server.use(http.get('*/api/records', () => new HttpResponse(null, { status: 500 })));
    renderWithProviders(<RecordsPage />, { route: '/records' });
    expect(screen.getByRole('status', { name: 'Loading records' })).toBeInTheDocument();
    expect(await screen.findByText('Records unavailable')).toBeInTheDocument();
  });

  it('every data chart exposes Table and CSV controls', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records' });
    for (const name of ['Most Sundays shot', 'Longest streaks']) {
      const region = await screen.findByRole('region', { name });
      expectChartControls(region);
      expect(
        await within(region).findByRole('img', { name: `${name} bar chart` }, LAZY),
      ).toBeVisible();
    }
    expect(screen.getAllByRole('button', { name: 'Table' })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: 'CSV' })).toHaveLength(2);
  });

  it('explains each chart, tagged with the time window it follows', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records?w=6m' });
    for (const name of ['Most Sundays shot', 'Longest streaks']) {
      const region = await screen.findByRole('region', { name });
      await expectExplainer(region, 'About this chart', { read: true });
      const user = userEvent.setup();
      await user.click(within(region).getByRole('button', { name: 'About this chart' }));
      expect(within(region).getAllByText(/^Last 6 months( · .+)?$/).length).toBeGreaterThan(0);
      expect(within(region).queryByText('All time')).toBeNull();
    }
  });

  it('says the rating record ignores round types and needs five rounds', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records' });
    const region = await screen.findByRole('region', { name: 'Highest rating in these dates' });
    expect(within(region).getByText(/All round types · needs 5 or more rounds/)).toBeVisible();
    expect(within(region).getByRole('columnheader', { name: 'Rating' })).toBeVisible();
  });

  it('uses plain Sunday wording and no jargon in the record tables', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records' });
    await screen.findByRole('table', { name: 'Highest scores' });
    expect(screen.getByRole('columnheader', { name: 'Above middle score' })).toBeVisible();
    expect(screen.queryByText(/median/i)).toBeNull();
    expect(screen.queryByText(/week-over-week/i)).toBeNull();
  });

  it('labels a shared display name with the shooter id in the chart table', async () => {
    server.use(
      http.get('*/api/records', () =>
        HttpResponse.json({
          ...recordsFixture,
          most_events: [
            { rank: 1, shooter_id: 4, display_name: 'Desmond', value: 12 },
            { rank: 2, shooter_id: 9, display_name: 'Desmond', value: 11 },
          ],
        }),
      ),
    );
    const { user } = renderWithProviders(<RecordsPage />, { route: '/records' });
    const region = await screen.findByRole('region', { name: 'Most Sundays shot' });
    await user.click(within(region).getByRole('button', { name: 'Table' }));
    const table = within(region).getByRole('table', { name: 'Most Sundays shot' });
    expect(within(table).getByRole('link', { name: 'Desmond #4' })).toHaveAttribute(
      'href',
      '/shooters/4',
    );
    expect(within(table).getByText('Desmond #9')).toBeInTheDocument();
  });

  it('opens the shooter from a chart bar, keeping the round-type filter', async () => {
    const { router } = renderWithProviders(<RecordsPage />, {
      route: '/records?rt=super_sporting',
    });
    const chart = await screen.findByRole('img', { name: 'Most Sundays shot bar chart' }, LAZY);
    getInstanceByDom(chart)?.trigger('click', { name: 'Ace, Amy' } as never);
    expect(router.state.location.pathname + router.state.location.search).toBe(
      '/shooters/7?rt=super_sporting',
    );
  });

  it('draws no value labels on the bars, which the wider grid margin would clip', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records' });
    const chart = await screen.findByRole('img', { name: 'Most Sundays shot bar chart' }, LAZY);
    const option = getInstanceByDom(chart)?.getOption() as {
      series: { label?: { show?: boolean } }[];
    };
    expect(option.series[0]?.label?.show).toBe(false);
  });

  it('links a chart table row to its shooter by id, not by a label lookup', async () => {
    server.use(
      http.get('*/api/records', () =>
        HttpResponse.json({
          ...recordsFixture,
          most_events: [
            { rank: 1, shooter_id: 4, display_name: 'Desmond', value: 12 },
            { rank: 2, shooter_id: 9, display_name: 'Desmond', value: 11 },
          ],
        }),
      ),
    );
    const { user } = renderWithProviders(<RecordsPage />, { route: '/records?rt=super_sporting' });
    const region = await screen.findByRole('region', { name: 'Most Sundays shot' });
    await user.click(within(region).getByRole('button', { name: 'Table' }));
    expect(within(region).getByRole('link', { name: 'Desmond #9' })).toHaveAttribute(
      'href',
      '/shooters/9?rt=super_sporting',
    );
  });

  it('ignores a click on something that is not a bar', async () => {
    const { router } = renderWithProviders(<RecordsPage />, { route: '/records' });
    const chart = await screen.findByRole('img', { name: 'Most Sundays shot bar chart' }, LAZY);
    getInstanceByDom(chart)?.trigger('click', { name: 'nobody' } as never);
    getInstanceByDom(chart)?.trigger('click', {} as never);
    expect(router.state.location.pathname).toBe('/records');
  });

  describe('full data in fullscreen and CSV', () => {
    /** The default answer holds 10 shooters per list; `limit=all` holds 13 (events) and 12 (streaks). */
    const shooters = (n: number) =>
      Array.from({ length: n }, (_, i) => ({
        rank: i + 1,
        shooter_id: 100 + i,
        display_name: `Shooter ${String(i + 1).padStart(2, '0')}`,
        value: 100 - i,
      }));
    function serveLimited(seen: URL[] = []) {
      server.use(
        http.get('*/api/records', ({ request }) => {
          const url = new URL(request.url);
          seen.push(url);
          const all = url.searchParams.has('limit');
          return HttpResponse.json({
            ...recordsFixture,
            most_events: shooters(all ? 13 : 10),
            longest_streaks: shooters(all ? 12 : 10),
            totals: { ...recordsFixture.totals, most_events: 13, longest_streaks: 12 },
          });
        }),
      );
      return seen;
    }
    const rowCount = (el: HTMLElement) => within(el).getAllByRole('row').length;
    const fullFetches = (seen: URL[]) => seen.filter((u) => u.searchParams.has('limit'));

    it('most Sundays: the fullscreen table and CSV list every shooter, the card the top ten', async () => {
      const seen = serveLimited();
      const csv = captureCsv();
      const { user } = renderWithProviders(<RecordsPage />, {
        route: '/records?rt=super_sporting&rec-events=table',
      });
      const card = await screen.findByRole('region', { name: 'Most Sundays shot' });
      expect(rowCount(card)).toBe(1 + 10);
      expect(fullFetches(seen)).toHaveLength(0);
      const dialog = await openFullscreen(user, card, 'Most Sundays shot');
      expect(await within(dialog).findByText('Every shooter.')).toBeInTheDocument();
      expect(rowCount(dialog)).toBe(1 + 13);
      const full = fullFetches(seen);
      expect(full).toHaveLength(1);
      // Only as many rows as the list has, never `all`.
      expect(full[0]?.searchParams.get('limit')).toBe('13');
      expect(full[0]?.searchParams.getAll('round_type')).toEqual(['super_sporting']);
      await user.click(within(card).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toEqual(['records-rec-events.csv']));
      expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(1 + 13);
      expect(fullFetches(seen)).toHaveLength(1);
    });

    it('longest streaks: the full data comes from its own list', async () => {
      const seen = serveLimited();
      const csv = captureCsv();
      const { user } = renderWithProviders(<RecordsPage />, {
        route: '/records?rec-streaks=table',
      });
      const card = await screen.findByRole('region', { name: 'Longest streaks' });
      expect(rowCount(card)).toBe(1 + 10);
      const dialog = await openFullscreen(user, card, 'Longest streaks');
      expect(await within(dialog).findByText('Every shooter.')).toBeInTheDocument();
      expect(rowCount(dialog)).toBe(1 + 12);
      // Each chart fetches once, and the two share nothing but the URL.
      expect(fullFetches(seen)).toHaveLength(1);
      await user.click(within(card).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toEqual(['records-rec-streaks.csv']));
      expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(1 + 12);
    });

    it('the full fetch carries the dates the page is asking for', async () => {
      const seen = serveLimited();
      const { user } = renderWithProviders(<RecordsPage />, {
        route: '/records?w=2024-01-07..2024-12-29',
      });
      const card = await screen.findByRole('region', { name: 'Most Sundays shot' });
      await openFullscreen(user, card, 'Most Sundays shot');
      await waitFor(() => expect(fullFetches(seen)).toHaveLength(1));
      const params = fullFetches(seen)[0]?.searchParams;
      expect(params?.get('since')).toBe('2024-01-07');
      expect(params?.get('as_of')).toBe('2024-12-29');
    });

    it('draws a bar for every shooter in fullscreen, tall enough for each label', async () => {
      serveLimited();
      const { user } = renderWithProviders(<RecordsPage />, { route: '/records' });
      const card = await screen.findByRole('region', { name: 'Most Sundays shot' });
      const bars = (el: HTMLElement) =>
        (
          (
            getInstanceByDom(within(el).getByRole('img', { name: /bar chart/ }))?.getOption() as {
              yAxis: { data: string[] }[];
            }
          ).yAxis[0] as { data: string[] }
        ).data.length;
      await within(card).findByRole('img', { name: /bar chart/ }, LAZY);
      expect(bars(card)).toBe(10);
      const dialog = await openFullscreen(user, card, 'Most Sundays shot');
      await within(dialog).findByRole('img', { name: /bar chart/ }, LAZY);
      await waitFor(() => expect(bars(dialog)).toBe(13), LAZY);
      expect(within(dialog).getByRole('img', { name: /bar chart/ })).toHaveStyle({
        height: `${80 + 28 * 13}px`,
      });
    }, 15_000);

    it('opens the shooter from any fullscreen bar, including past the top ten and namesakes', async () => {
      server.use(
        http.get('*/api/records', ({ request }) => {
          const all = new URL(request.url).searchParams.has('limit');
          const list = shooters(all ? 13 : 10);
          // The 13th shooter shares the first one's name, so the full labels become "Name #id".
          if (all)
            list[12] = { ...shooters(13)[12], display_name: 'Shooter 01' } as (typeof list)[number];
          return HttpResponse.json({ ...recordsFixture, most_events: list });
        }),
      );
      const { user, router } = renderWithProviders(<RecordsPage />, { route: '/records' });
      const card = await screen.findByRole('region', { name: 'Most Sundays shot' });
      const dialog = await openFullscreen(user, card, 'Most Sundays shot');
      const chart = await within(dialog).findByRole('img', { name: /bar chart/ }, LAZY);
      await waitFor(() => {
        const axis = (getInstanceByDom(chart)?.getOption() as { yAxis: { data: string[] }[] })
          .yAxis[0]?.data;
        expect(axis).toHaveLength(13);
      }, LAZY);
      const go = () => router.state.location.pathname;
      getInstanceByDom(chart)?.trigger('click', { name: 'Shooter 01 #112' } as never);
      expect(go()).toBe('/shooters/112');
      void router.navigate('/records');
      await waitFor(() => expect(go()).toBe('/records'));
      getInstanceByDom(chart)?.trigger('click', { name: 'Shooter 01 #100' } as never);
      expect(go()).toBe('/shooters/100');
    }, 15_000);
  });

  describe('the header window', () => {
    function capture(body: RecordsOut = recordsFixture): URL[] {
      const seen: URL[] = [];
      server.use(
        http.get('*/api/records', ({ request }) => {
          seen.push(new URL(request.url));
          return HttpResponse.json(body);
        }),
      );
      return seen;
    }

    function last(seen: URL[]): URLSearchParams {
      const url = seen.at(-1);
      if (url === undefined) throw new Error('no /api/records request yet');
      return url.searchParams;
    }

    it('has no date controls of its own', async () => {
      renderWithProviders(<RecordsPage />, { route: '/records' });
      await screen.findByRole('table', { name: 'Highest scores' });
      expect(screen.queryByRole('group', { name: 'Dates' })).toBeNull();
      expect(screen.queryByLabelText('Start date')).toBeNull();
      expect(screen.queryByLabelText('End date')).toBeNull();
    });

    it('opens on the last 8 weeks, sends its dates, and prints them under the title', async () => {
      const seen = capture();
      renderWithProviders(<RecordsPage />, { route: '/records' });
      await screen.findByRole('table', { name: 'Highest scores' });
      expect(last(seen).get('since')).toBe('2026-08-03');
      expect(last(seen).get('as_of')).toBe('2026-09-27');
      expect(last(seen).has('limit')).toBe(false);
      expect(screen.getByText('Last 8 weeks · Aug 3 – Sep 27', { selector: 'p' })).toBeVisible();
    });

    it.each([
      ['/records?w=12m', 'Last 12 months', '2025-09-28'],
      ['/records?w=ytd', 'This year to date', '2026-01-01'],
      ['/records?w=3m', 'Last 3 months', '2026-06-28'],
    ])('%s asks for records since %s', async (route, label, since) => {
      const seen = capture();
      renderWithProviders(<RecordsPage />, { route });
      await screen.findByRole('table', { name: 'Highest scores' });
      expect(last(seen).get('since')).toBe(since);
      expect(screen.getByText(new RegExp(`^${label} · [^·]*$`), { selector: 'p' })).toBeVisible();
    });

    it('All time sends no start date and starts its dates on the first Sunday', async () => {
      const seen = capture();
      renderWithProviders(<RecordsPage />, { route: '/records?w=all' });
      await screen.findByRole('table', { name: 'Highest scores' });
      expect(last(seen).has('since')).toBe(false);
      expect(last(seen).get('as_of')).toBe('2026-09-27');
      expect(screen.getByText(/^All time · .* – Sep 27, 2026$/, { selector: 'p' })).toBeVisible();
    });

    it('a Custom window sends its own dates and shows them alone', async () => {
      const seen = capture();
      renderWithProviders(<RecordsPage />, { route: '/records?w=2024-01-07..2024-12-29' });
      await screen.findByRole('table', { name: 'Highest scores' });
      expect(last(seen).get('since')).toBe('2024-01-07');
      expect(last(seen).get('as_of')).toBe('2024-12-29');
      expect(screen.getByText('Jan 7, 2024 – Dec 29, 2024', { selector: 'p' })).toBeVisible();
    });

    it('puts the period in every card subtitle', async () => {
      renderWithProviders(<RecordsPage />, { route: '/records' });
      await screen.findByRole('table', { name: 'Highest scores' });
      for (const name of [
        'Highest scores',
        'Perfect 50s',
        'Biggest day vs the field',
        'Biggest jump from one Sunday to the next',
        'Most Sundays shot',
        'Longest streaks',
        'Highest rating in these dates',
      ]) {
        const card = screen.getByRole('region', { name });
        expect(within(card).getAllByText(/Last 8 weeks · Aug 3 – Sep 27/)[0], name).toBeVisible();
      }
    });

    it('starts an All time window on the window end when the first Sunday is unknown', async () => {
      server.use(
        http.get('*/api/meta', () =>
          HttpResponse.json({ first_event_date: null, last_score_date: '2026-09-27' }),
        ),
      );
      capture();
      renderWithProviders(<RecordsPage />, { route: '/records?w=all' });
      await screen.findByRole('table', { name: 'Highest scores' });
      expect(screen.getByText('All time · Sep 27 – Sep 27', { selector: 'p' })).toBeVisible();
    });

    it('waits for the latest Sunday before it asks', async () => {
      server.use(http.get('*/api/meta', () => new Promise(() => undefined)));
      const seen = capture();
      renderWithProviders(<RecordsPage />, { route: '/records' });
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(seen).toHaveLength(0);
      expect(screen.getByRole('status', { name: 'Loading records' })).toBeInTheDocument();
    });

    it('says so in plain words, and widens to 12M, when nothing was shot in the window', async () => {
      const seen = capture({
        ...recordsFixture,
        highest_scores: [],
        totals: { ...recordsFixture.totals, highest_scores: 0 },
      });
      const { user, router } = renderWithProviders(<RecordsPage />, { route: '/records' });
      expect(await screen.findByText('No scored rounds in the last 8 weeks')).toBeVisible();
      expect(screen.queryByRole('table', { name: 'Highest scores' })).toBeNull();
      await user.click(screen.getByRole('button', { name: '12M' }));
      expect(router.state.location.search).toBe('?w=12m');
      await waitFor(() => {
        expect(last(seen).get('since')).toBe('2025-09-28');
      });
      expect(screen.getByRole('button', { name: 'All' })).toBeVisible();
    });

    it('reads a list the server sent no size for as empty, and no tie as none', async () => {
      capture({ ...recordsFixture, totals: {}, tied_more: {} });
      renderWithProviders(<RecordsPage />, { route: '/records' });
      expect(await screen.findByText('No scored rounds in the last 8 weeks')).toBeVisible();
    });

    it('reads a missing tie count as no tie', async () => {
      capture({ ...recordsFixture, tied_more: {} });
      renderWithProviders(<RecordsPage />, { route: '/records' });
      await screen.findByRole('table', { name: 'Highest scores' });
      expect(screen.queryByText(/more tied at/)).toBeNull();
    });

    it('offers no widening from All time', async () => {
      capture({
        ...recordsFixture,
        highest_scores: [],
        totals: { ...recordsFixture.totals, highest_scores: 0 },
      });
      renderWithProviders(<RecordsPage />, { route: '/records?w=all' });
      expect(await screen.findByText('No scored rounds in all time')).toBeVisible();
      expect(screen.queryByRole('group', { name: 'Widen the window' })).toBeNull();
    });
  });

  describe('old URLs convert once into the window', () => {
    it.each([
      ['?rp=all', '?w=all', null],
      ['?rp=ytd', '?w=ytd', '2026-01-01'],
      ['?rp=custom&since=2024-01-07&as_of=2024-12-29', '?w=2024-01-07..2024-12-29', '2024-01-07'],
      ['?rp=custom&since=2024-01-07', '?w=2024-01-07..2026-09-27', '2024-01-07'],
      ['?rp=custom', '?w=2020-01-05..2026-09-27', '2020-01-05'],
      ['?rp=custom&since=2024-12-29&as_of=2024-01-07', '', '2026-08-03'],
      ['?since=2024-01-07&as_of=2024-12-29', '', '2026-08-03'],
      ['?rp=ytd&rt=sporting', '?rt=sporting&w=ytd', '2026-01-01'],
    ])('%s becomes "%s"', async (old, search, since) => {
      const seen: URL[] = [];
      server.use(
        http.get('*/api/meta', () =>
          HttpResponse.json({ first_event_date: '2020-01-05', last_score_date: '2026-09-27' }),
        ),
        http.get('*/api/records', ({ request }) => {
          seen.push(new URL(request.url));
          return HttpResponse.json(recordsFixture);
        }),
      );
      const { router } = renderWithProviders(<RecordsPage />, { route: `/records${old}` });
      await screen.findByRole('table', { name: 'Highest scores' });
      expect(router.state.location.search).toBe(search);
      expect(seen.at(-1)?.searchParams.get('since') ?? null).toBe(
        since === '2026-08-03' ? since : since,
      );
      // Never a request for the wrong window first.
      expect(new Set(seen.map((url) => url.search)).size).toBe(1);
    });

    it('an explicit w beats an old rp, which is still removed', async () => {
      const { router } = renderWithProviders(<RecordsPage />, { route: '/records?w=6m&rp=ytd' });
      await screen.findByRole('table', { name: 'Highest scores' });
      expect(router.state.location.search).toBe('?w=6m');
    });
  });

  describe('Show all N, and ties at the cut', () => {
    const rounds = (n: number, value = 49) =>
      Array.from({ length: n }, (_, i) => ({
        rank: 1,
        shooter_id: 100 + i,
        display_name: `Shooter ${String(i + 1).padStart(2, '0')}`,
        event_date: '2026-09-27',
        value,
      }));

    /** The default answer holds 10 rows of a 14-row list (two tied at the cut); `limit=all` holds all 14. */
    function serveLists(seen: URL[] = []) {
      server.use(
        http.get('*/api/records', ({ request }) => {
          const url = new URL(request.url);
          seen.push(url);
          const all = url.searchParams.has('limit');
          const cut = all ? 14 : 10;
          return HttpResponse.json({
            ...recordsFixture,
            highest_scores: rounds(cut),
            perfect_rounds: rounds(cut, 50),
            totals: { ...recordsFixture.totals, highest_scores: 14, perfect_rounds: 14 },
            tied_more: { ...recordsFixture.tied_more, highest_scores: all ? 0 : 4 },
          });
        }),
      );
      return seen;
    }

    it('shows ten rows, the tie the cut leaves out, and asks for the rest only when pressed', async () => {
      const seen = serveLists();
      const { user } = renderWithProviders(<RecordsPage />, { route: '/records' });
      const card = await screen.findByRole('region', { name: 'Highest scores' });
      expect(within(card).getAllByRole('row')).toHaveLength(1 + 10);
      expect(within(card).getByText('4 more tied at 49')).toBeVisible();
      expect(seen.filter((u) => u.searchParams.has('limit'))).toHaveLength(0);
      await user.click(within(card).getByRole('button', { name: 'Show all 14' }));
      await waitFor(() => {
        expect(within(card).getAllByRole('row')).toHaveLength(1 + 14);
      });
      expect(seen.filter((u) => u.searchParams.get('limit') === '14')).toHaveLength(1);
      expect(within(card).queryByText(/more tied at/)).toBeNull();
      await user.click(within(card).getByRole('button', { name: 'Show fewer' }));
      expect(within(card).getAllByRole('row')).toHaveLength(1 + 10);
    });

    it('carries the window and round type on the full fetch', async () => {
      const seen = serveLists();
      const { user } = renderWithProviders(<RecordsPage />, {
        route: '/records?w=6m&rt=super_sporting',
      });
      const card = await screen.findByRole('region', { name: 'Highest scores' });
      await user.click(within(card).getByRole('button', { name: 'Show all 14' }));
      await waitFor(() => {
        expect(seen.some((u) => u.searchParams.has('limit'))).toBe(true);
      });
      const full = seen.find((u) => u.searchParams.has('limit'))?.searchParams;
      expect(full?.get('since')).toBe('2026-03-28');
      expect(full?.get('as_of')).toBe('2026-09-27');
      expect(full?.getAll('round_type')).toEqual(['super_sporting']);
    });

    it('Perfect 50s is newest first: the latest ten and a count, the rest on Show all', async () => {
      serveLists();
      const { user } = renderWithProviders(<RecordsPage />, { route: '/records' });
      const card = await screen.findByRole('region', { name: 'Perfect 50s' });
      expect(within(card).getAllByRole('listitem')).toHaveLength(10);
      expect(within(card).getByText(/newest first\. The latest 10 of 14\./)).toBeVisible();
      expect(within(card).queryByText(/more tied at/)).toBeNull();
      await user.click(within(card).getByRole('button', { name: 'Show all 14' }));
      await waitFor(() => {
        expect(within(card).getAllByRole('listitem')).toHaveLength(14);
      });
    });

    it('a list that fits has no Show all', async () => {
      renderWithProviders(<RecordsPage />, { route: '/records' });
      const card = await screen.findByRole('region', { name: 'Highest scores' });
      expect(within(card).queryByRole('button', { name: /Show all/ })).toBeNull();
    });

    it('tells a failed fetch apart, and asks again on the next press', async () => {
      let fail = true;
      server.use(
        http.get('*/api/records', ({ request }) => {
          if (new URL(request.url).searchParams.has('limit')) {
            if (fail) return new HttpResponse(null, { status: 500 });
            return HttpResponse.json({ ...recordsFixture, highest_scores: rounds(14) });
          }
          return HttpResponse.json({
            ...recordsFixture,
            highest_scores: rounds(10),
            totals: { ...recordsFixture.totals, highest_scores: 14 },
          });
        }),
      );
      const { user } = renderWithProviders(<RecordsPage />, { route: '/records' });
      const card = await screen.findByRole('region', { name: 'Highest scores' });
      await user.click(within(card).getByRole('button', { name: 'Show all 14' }));
      expect(await within(card).findByRole('alert')).toHaveTextContent(
        'Could not load the full list. Try again.',
      );
      fail = false;
      await user.click(within(card).getByRole('button', { name: 'Show all 14' }));
      await waitFor(() => {
        expect(within(card).getAllByRole('row')).toHaveLength(1 + 14);
      });
    });

    it('a list longer than the server allows shows its top 500', async () => {
      const seen: URL[] = [];
      server.use(
        http.get('*/api/records', ({ request }) => {
          const url = new URL(request.url);
          seen.push(url);
          const limit = url.searchParams.get('limit');
          return HttpResponse.json({
            ...recordsFixture,
            highest_scores: rounds(limit === '500' ? 500 : 10),
            totals: { ...recordsFixture.totals, highest_scores: 14000 },
          });
        }),
      );
      const { user } = renderWithProviders(<RecordsPage />, { route: '/records' });
      const card = await screen.findByRole('region', { name: 'Highest scores' });
      await user.click(within(card).getByRole('button', { name: 'Show top 500 of 14000' }));
      expect(await within(card).findByText('Showing the top 500 of 14000.')).toBeVisible();
      expect(seen.some((u) => u.searchParams.get('limit') === '500')).toBe(true);
    });

    it.each([
      ['Biggest day vs the field', 'biggest_adjusted', '+18.0'],
      ['Biggest jump from one Sunday to the next', 'biggest_jumps', '+30'],
      ['Highest scores', 'highest_scores', '50'],
    ] as const)(
      '%s: names the tie in its own format, and Show all lists the rest',
      async (title, list, tie) => {
        const short = recordsFixture[list];
        const long = [...short, ...short];
        server.use(
          http.get('*/api/records', ({ request }) => {
            const all = new URL(request.url).searchParams.has('limit');
            return HttpResponse.json({
              ...recordsFixture,
              [list]: all ? long : short,
              totals: { ...recordsFixture.totals, [list]: long.length },
              tied_more: { ...recordsFixture.tied_more, [list]: all ? 0 : 1 },
            });
          }),
        );
        const { user } = renderWithProviders(<RecordsPage />, { route: '/records' });
        const card = await screen.findByRole('region', { name: title });
        const last = short.at(-1);
        expect(
          within(card).getByText(
            new RegExp(
              `^1 more tied at ${tie === '50' ? String(last?.value) : tie.replace('+', '\\+')}$`,
            ),
          ),
        ).toBeVisible();
        await user.click(
          within(card).getByRole('button', { name: `Show all ${String(long.length)}` }),
        );
        await waitFor(() => {
          expect(within(card).getAllByRole('row')).toHaveLength(1 + long.length);
        });
      },
    );

    it('Highest ratings stays a top-ten record: no Show all and no tie note', async () => {
      server.use(
        http.get('*/api/records', () =>
          HttpResponse.json({
            ...recordsFixture,
            totals: { ...recordsFixture.totals, highest_ratings: 285 },
            tied_more: { ...recordsFixture.tied_more, highest_ratings: 3 },
          }),
        ),
      );
      renderWithProviders(<RecordsPage />, { route: '/records' });
      const card = await screen.findByRole('region', { name: 'Highest rating in these dates' });
      expect(within(card).queryByRole('button', { name: /Show/ })).toBeNull();
      expect(within(card).queryByText(/more tied at/)).toBeNull();
    });

    it('a filled subtitle stays short when nothing is cut', async () => {
      renderWithProviders(<RecordsPage />, { route: '/records' });
      const card = await screen.findByRole('region', { name: 'Most Sundays shot' });
      expect(within(card).getByText(/Top 2$/)).toBeVisible();
    });

    it('names the tie in a chart card subtitle, and the total', async () => {
      server.use(
        http.get('*/api/records', () =>
          HttpResponse.json({
            ...recordsFixture,
            totals: { ...recordsFixture.totals, most_events: 40 },
            tied_more: { ...recordsFixture.tied_more, most_events: 3 },
          }),
        ),
      );
      renderWithProviders(<RecordsPage />, { route: '/records' });
      const card = await screen.findByRole('region', { name: 'Most Sundays shot' });
      expect(within(card).getByText(/Top 2 of 40 · 3 more tied at 267/)).toBeVisible();
    });
  });
});

describe('RecordsPage insight targets', () => {
  it('rings the highest-score row an insight points to', async () => {
    renderWithProviders(<RecordsPage />, {
      route: '/records?rec-highest.hl=2022-12-04,s:3#chart-rec-highest',
    });
    const table = await screen.findByRole('table', { name: 'Highest scores' });
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((r) => r.getAttribute('aria-current'))).toEqual([null, 'true', null]);
    expect(screen.getByRole('region', { name: 'Highest scores' })).toHaveAttribute(
      'id',
      'chart-rec-highest',
    );
  });

  it('explains the highest-score table', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records' });
    const card = await screen.findByRole('region', { name: 'Highest scores' });
    expect(within(card).getByRole('button', { name: /About this table/ })).toBeInTheDocument();
  });
});
