import { screen, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { expectChartControls, expectExplainer } from '../../../test/charts';

// The heatmap (and ECharts) load on demand; a cold import can outlast findBy's 1 s default when the
// suite runs alongside others, so waits for it get a longer timeout.
import { server } from '../../../test/msw/server';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { renderWithProviders } from '../../../test/render';
import type { EventDetail, Notable, StationMatrix } from '../api';
import { attendanceOnlyDetail, eventDetail, eventSummaries, specialDetail } from '../mocks';
import type { EventSection } from '../sections';
import { EventDetailPage } from './EventDetailPage';

function renderEvent(detail: EventDetail | null, sections: EventSection[] = [], query = '') {
  server.use(
    http.get('*/api/events/:date', () =>
      detail
        ? HttpResponse.json(detail)
        : HttpResponse.json(
            { error: { code: 'event_not_found', message: 'No event on 2026-09-20' } },
            { status: 404 },
          ),
    ),
  );
  const date = detail?.event_date ?? '2026-09-20';
  return renderWithProviders(
    <Routes>
      <Route path="/events/:date" element={<EventDetailPage sections={sections} />} />
    </Routes>,
    { route: `/events/${date}${query}` },
  );
}

/** Headings start at h1 and never skip a level (h1 → h3). */
function expectUnbrokenOutline(): void {
  const levels = [...document.querySelectorAll('h1, h2, h3, h4, h5, h6')].map((h) =>
    Number(h.tagName.slice(1)),
  );
  expect(levels[0]).toBe(1);
  expect(levels.filter((level, i) => i > 0 && level > (levels[i - 1] ?? 0) + 1)).toEqual([]);
}

function renderAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/events/:date" element={<EventDetailPage sections={[]} />} />
    </Routes>,
    { route },
  );
}

describe('EventDetailPage', () => {
  it('shows the header, stats and results for a scored event', async () => {
    renderEvent(eventDetail);
    expect(await screen.findByText('Super Sporting')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Sep 13, 2026' })).toBeInTheDocument();
    expect(screen.getByText(/\(from station sheets\)/)).toBeInTheDocument();
    const glance = screen.getByRole('region', { name: 'This Sunday' });
    const difficulty = within(glance).getByText('Difficulty').closest('div')?.parentElement;
    expect(difficulty).toHaveTextContent('+2.1');
    expect(difficulty).toHaveTextContent('harder than a typical Sunday');
    const results = screen.getByRole('table', { name: 'Results' });
    expect(within(results).getAllByRole('row')).toHaveLength(5);
    expect(within(results).getByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/3',
    );
  });

  it('every data chart exposes Table and CSV controls', async () => {
    renderEvent(eventDetail);
    // The station heatmap is the page's only data chart (loaded on demand).
    expect(await screen.findAllByRole('button', { name: 'CSV' }, LAZY_CHART)).toHaveLength(1);
    expectChartControls(screen.getByRole('region', { name: 'Station hits' }));
  });

  it(
    'explains the station heatmap, without a time-window tag (it is one Sunday)',
    async () => {
      renderEvent(eventDetail);
      await screen.findByRole('button', { name: 'CSV' }, LAZY_CHART);
      const region = screen.getByRole('region', { name: 'Station hits' });
      await expectExplainer(region, 'About this chart', { read: true });
      expect(within(region).queryByText('All time')).not.toBeInTheDocument();
    },
    LAZY_TEST_TIMEOUT,
  );

  it('explains the results table, each tile and the weather', async () => {
    renderEvent(eventDetail);
    await screen.findByRole('table', { name: 'Results' });
    await expectExplainer(screen.getByRole('region', { name: 'Results' }), 'About these results', {
      read: true,
    });
    const glance = screen.getByRole('region', { name: 'This Sunday' });
    for (const stat of ['Shooters', 'Head count', 'Median', 'Top score', 'Difficulty']) {
      await expectExplainer(glance, `About ${stat}`);
    }
    await expectExplainer(
      screen.getByRole('region', { name: 'Weather (10:00–12:00)' }),
      'About this weather',
    );
    await expectExplainer(
      screen.getByRole('region', { name: 'vs previous Sunday' }),
      'About this comparison',
    );
    // The fixture's only notable is a personal best, which the insights tell (Plan 12 Phase 3 T3).
    expect(screen.queryByRole('region', { name: 'Notables' })).not.toBeInTheDocument();
  });

  it('keeps the outline unbroken with an explainer open', async () => {
    const { user } = renderEvent(eventDetail);
    await screen.findByRole('table', { name: 'Results' });
    await user.click(screen.getByRole('button', { name: 'About these results' }));
    await user.click(screen.getByRole('button', { name: 'About Median' }));
    expectUnbrokenOutline();
  });

  it('compares with the previous Sunday and names its date', async () => {
    renderEvent(eventDetail);
    const card = await screen.findByRole('region', { name: 'vs previous Sunday' });
    expect(within(card).getByText(/previous Sunday with full results/)).toBeInTheDocument();
    expect(within(card).getByRole('link', { name: 'Sep 6, 2026' })).toBeInTheDocument();
    expect(screen.queryByText('vs last week')).not.toBeInTheDocument();
  });

  it('leaves personal bests to the insights, so no Notables card shows', async () => {
    renderEvent(eventDetail);
    await screen.findByRole('table', { name: 'Results' });
    expect(screen.queryByRole('region', { name: 'Notables' })).not.toBeInTheDocument();
    expect(screen.queryByText(/New personal best 42/)).not.toBeInTheDocument();
  });

  it('shows a dash for the rating change on a partial-results Sunday', async () => {
    const [first, ...rest] = eventDetail.results;
    if (!first) throw new Error('fixture has results');
    renderEvent({
      ...eventDetail,
      results_complete: false,
      head_count: 30,
      results: [{ ...first, mu_after: first.mu_before, rating_delta: 0 }, ...rest],
    });
    const results = await screen.findByRole('table', { name: 'Results' });
    const row = within(results).getByRole('row', { name: /Nordquist, Sherman/ });
    expect(within(row).getAllByRole('cell').at(-1)).toHaveTextContent('—');
  });

  it('subtitles the heatmap with only what the chart shows', async () => {
    renderEvent(eventDetail);
    expect(await screen.findByText('Hits per shooter at each station')).toBeInTheDocument();
    expect(screen.queryByText(/targets in brackets|in the table/)).not.toBeInTheDocument();
  });

  it('keeps an unbroken heading outline on a scored event', async () => {
    renderEvent(eventDetail, [
      { id: 'extra', title: 'Extra', order: 10, Component: () => <p>extra</p> },
    ]);
    await screen.findByRole('button', { name: 'CSV' }, LAZY_CHART);
    expectUnbrokenOutline();
  });

  it('shows the date as the page heading while the event loads', async () => {
    server.use(http.get('*/api/events/:date', () => delay('infinite')));
    renderAt('/events/2026-09-13');
    expect(screen.getByRole('heading', { level: 1, name: 'Sep 13, 2026' })).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument();
  });

  it('sizes the station heatmap to its rows', async () => {
    const stations = eventDetail.stations as StationMatrix;
    const [first] = stations.entries;
    if (!first) throw new Error('fixture has station entries');
    const entries = Array.from({ length: 24 }, (_, i) => ({ ...first, entry_row: 10 + i }));
    renderEvent({ ...eventDetail, stations: { ...stations, entries } });
    expect(
      await screen.findByRole('img', { name: 'Station hits heatmap for Sep 13, 2026' }, LAZY_CHART),
    ).toHaveStyle({ height: '600px' });
  });

  it('shows weather, the comparison with last week and notables', async () => {
    renderEvent(eventDetail);
    expect(await screen.findByText('Partly cloudy')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sep 6, 2026' })).toHaveAttribute(
      'href',
      '/events/2026-09-06',
    );
    expect(screen.getByText('−11')).toBeInTheDocument();
    // Personal bests and first rounds are told by the Sunday's insights (Plan 12 Phase 3 T3).
    expect(screen.queryByText('Personal best')).not.toBeInTheDocument();
  });

  it('keeps the global round-type filter on its links', async () => {
    renderEvent(eventDetail, [], '?rt=sporting');
    expect(await screen.findByRole('link', { name: 'Sep 6, 2026' })).toHaveAttribute(
      'href',
      '/events/2026-09-06?rt=sporting',
    );
    const results = screen.getByRole('table', { name: 'Results' });
    for (const link of within(results).getAllByRole('link', { name: 'Nordquist, Sherman' })) {
      expect(link).toHaveAttribute('href', '/shooters/12?rt=sporting');
    }
  });

  it('attendance-only event shows the head count empty state', async () => {
    renderEvent(attendanceOnlyDetail);
    expect(
      await screen.findByRole('heading', {
        level: 2,
        name: 'Attendance only — 7 shooters, no scores recorded',
      }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('table', { name: 'Results' })).not.toBeInTheDocument();
    expect(screen.getByText('No weather recorded for this Sunday')).toBeInTheDocument();
    expectUnbrokenOutline();
  });

  it('station-only date says no scores recorded', async () => {
    renderEvent({ ...attendanceOnlyDetail, event_date: '2026-10-04', head_count: null });
    expect(await screen.findByText('No scores recorded for this Sunday')).toBeInTheDocument();
  });

  it('incomplete event shows the partial results note', async () => {
    renderEvent({
      ...eventDetail,
      event_date: '2024-11-10',
      results_complete: false,
      head_count: 27,
      n_shooters: 7,
    });
    expect(
      await screen.findByText('Partial results — 7 of 27 shooters recorded.'),
    ).toBeInTheDocument();
  });

  it('a scored event without a head count shows a dash and no partial results note', async () => {
    renderEvent({ ...eventDetail, head_count: null, results_complete: false, vs_prev: null });
    expect(await screen.findByText('Head count')).toBeInTheDocument();
    expect(screen.getByText('Head count').closest('div')?.parentElement).toHaveTextContent(
      /Head count.*—/,
    );
    expect(screen.queryByText(/Partial results/)).not.toBeInTheDocument();
  });

  it('shows empty states when weather, stations, a previous event and notables are missing', async () => {
    renderEvent({
      ...eventDetail,
      round_type_source: 'override',
      weather: null,
      stations: null,
      vs_prev: null,
      notables: [],
    });
    expect(await screen.findByText(/\(admin override\)/)).toBeInTheDocument();
    expect(screen.getByText('No weather recorded for this Sunday')).toBeInTheDocument();
    expect(screen.getByText('First Sunday on record — nothing to compare.')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Notables' })).not.toBeInTheDocument();
    // No station sheet: no empty "Station hits" card and no chart controls.
    expect(screen.queryByRole('region', { name: 'Station hits' })).not.toBeInTheDocument();
    expect(screen.queryByText(/station/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /csv/i })).not.toBeInTheDocument();
  });

  it('a date without an event says so and links back to the calendar', async () => {
    renderEvent(null, [], '?rt=sporting');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Nothing on file for Sep 20, 2026' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'calendar' })).toHaveAttribute(
      'href',
      '/events?rt=sporting',
    );
    expectUnbrokenOutline();
  });

  it.each(['0', 'abc', '2026-02-30', '2026-09-20T00:00:00', '2026-9-20'])(
    'a crafted date %j shows the not-found state without asking the server',
    async (param) => {
      const requested: string[] = [];
      server.use(
        http.get('*/api/events/:date', ({ params }) => {
          requested.push(String(params.date));
          return HttpResponse.json(
            { error: { code: 'event_not_found', message: 'No event' } },
            { status: 404 },
          );
        }),
      );
      renderAt(`/events/${param}`);
      expect(
        await screen.findByRole('heading', { level: 1, name: 'Sunday not found' }),
      ).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'calendar' })).toHaveAttribute('href', '/events');
      expect(requested).toEqual([]);
      expectUnbrokenOutline();
    },
  );

  it('a date the server rejects (422) shows the not-found state', async () => {
    server.use(
      http.get('*/api/events/:date', () =>
        HttpResponse.json(
          { detail: [{ type: 'date_parsing', msg: 'year 0 is out of range' }] },
          { status: 422 },
        ),
      ),
    );
    renderAt('/events/0000-01-01');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sunday not found' }),
    ).toBeInTheDocument();
  });

  it('a server error shows a load failure', async () => {
    server.use(
      http.get('*/api/events/:date', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    renderAt('/events/2026-09-13');
    expect(
      await screen.findByRole('heading', { level: 1, name: "Couldn't load this Sunday" }),
    ).toBeInTheDocument();
    expect(screen.getByText('Internal server error')).toBeInTheDocument();
    expectUnbrokenOutline();
  });

  it('a network failure shows a load failure', async () => {
    server.use(http.get('*/api/events/:date', () => HttpResponse.error()));
    renderAt('/events/2026-09-13');
    expect(
      await screen.findByRole('heading', { level: 1, name: "Couldn't load this Sunday" }),
    ).toBeInTheDocument();
  });

  it('shows an unrecognised notable kind verbatim', async () => {
    // Plan 06 only sends pb / first_timer; a newer server kind must still render (cast: outside the union).
    const future = {
      kind: 'milestone',
      shooter_id: 7,
      display_name: 'Abernathy, Preston',
      detail: '250 events',
      value: 250,
    };
    renderEvent({ ...eventDetail, notables: [future as unknown as Notable] });
    expect(await screen.findByText('milestone')).toBeInTheDocument();
  });

  it('renders registered event sections with the event date', async () => {
    renderEvent(eventDetail, [
      {
        id: 'trophies',
        title: 'Trophies earned today',
        order: 10,
        Component: ({ date }) => <p>trophies for {date}</p>,
      },
    ]);
    expect(await screen.findByText('trophies for 2026-09-13')).toBeInTheDocument();
    expect(screen.getByText('Trophies earned today')).toBeInTheDocument();
  });

  it('renders top sections above the results, which are the chart-results anchor', async () => {
    renderEvent(eventDetail, [
      {
        id: 'insights',
        title: 'About this Sunday',
        order: 1,
        placement: 'top',
        Component: ({ date }) => <p>about {date}</p>,
      },
    ]);
    const top = await screen.findByRole('region', { name: 'About this Sunday' });
    const results = screen.getByRole('region', { name: 'Results' });
    expect(results).toHaveAttribute('id', 'chart-results');
    expect(top.compareDocumentPosition(results) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('focuses the results and marks the shooters an insight links to', async () => {
    renderEvent(eventDetail, [], '?results.hl=s:3#chart-results');
    const results = await screen.findByRole('region', { name: 'Results' });
    expect(results).toHaveFocus();
    const marked = within(results)
      .getAllByRole('row')
      .filter((row) => row.getAttribute('aria-current') === 'true');
    expect(marked.length).toBeGreaterThan(0);
  });

  it('steps to the previous and next Sunday with scores, keeping the filter', async () => {
    server.use(http.get('*/api/events', () => HttpResponse.json(eventSummaries)));
    renderEvent({ ...eventDetail, event_date: '2026-09-13' }, [], '?rt=sporting');
    const nav = await screen.findByRole('navigation', { name: 'Other Sundays' });
    expect(within(nav).getByRole('link', { name: /Previous Sunday/ })).toHaveAttribute(
      'href',
      '/events/2026-09-06?rt=sporting',
    );
    expect(within(nav).getByRole('link', { name: /Next Sunday/ })).toHaveAttribute(
      'href',
      '/events/2026-09-27?rt=sporting',
    );
  });

  it('has no next button on the latest Sunday and no previous on the first', async () => {
    server.use(http.get('*/api/events', () => HttpResponse.json(eventSummaries)));
    const { unmount } = renderEvent({ ...eventDetail, event_date: '2026-09-27' });
    const nav = await screen.findByRole('navigation', { name: 'Other Sundays' });
    expect(within(nav).queryByRole('link', { name: /Next Sunday/ })).not.toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: /Previous Sunday/ })).toBeInTheDocument();
    unmount();
    server.use(
      http.get('*/api/events', () =>
        HttpResponse.json(eventSummaries.filter((e) => e.event_date >= '2026-09-06')),
      ),
    );
    renderEvent({ ...eventDetail, event_date: '2026-09-06' });
    const first = await screen.findByRole('navigation', { name: 'Other Sundays' });
    expect(within(first).queryByRole('link', { name: /Previous Sunday/ })).not.toBeInTheDocument();
    expect(within(first).getByRole('link', { name: /Next Sunday/ })).toBeInTheDocument();
  });

  it('shows no Sunday buttons when there is no other Sunday with scores', async () => {
    server.use(http.get('*/api/events', () => HttpResponse.json([])));
    renderEvent(eventDetail);
    await screen.findByRole('heading', { level: 1 });
    expect(screen.queryByRole('navigation', { name: 'Other Sundays' })).not.toBeInTheDocument();
  });

  describe('a special Sunday (Plan 17)', () => {
    it('names the shoot and its targets in the header, with no round type', async () => {
      renderEvent(specialDetail);
      expect(await screen.findByText('3-Bird Shoot · Special · 60 targets')).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 1, name: 'Sep 20, 2026' })).toBeInTheDocument();
      expect(screen.queryByText('Sporting')).not.toBeInTheDocument();
    });

    it('takes the name and the target total from the data, not from a fixed shoot', async () => {
      renderEvent({ ...specialDetail, label: 'Flurry', target_total: 75 });
      expect(await screen.findByText('Flurry · Special · 75 targets')).toBeInTheDocument();
      const glance = screen.getByRole('region', { name: 'This Sunday' });
      expect(within(glance).getByText('Targets').closest('div')?.parentElement).toHaveTextContent(
        '75',
      );
      expect(
        within(screen.getByRole('table', { name: 'Results' })).getByRole('columnheader', {
          name: 'Score (of 75)',
        }),
      ).toBeVisible();
    });

    it('focuses the results when the link names them, as a scored Sunday does', async () => {
      renderEvent(specialDetail, [], '#chart-results');
      expect(await screen.findByRole('region', { name: 'Results' })).toHaveFocus();
    });

    it('explains special shoots once, and explains Stations', async () => {
      renderEvent(specialDetail);
      await screen.findByRole('table', { name: 'Results' });
      // The special-shoot explainer opens from the Targets stat only, not again on the Results card.
      expect(
        screen.getAllByRole('button', { name: /^About (Targets|special shoots)$/ }),
      ).toHaveLength(1);
      const glance = screen.getByRole('region', { name: 'This Sunday' });
      await expectExplainer(glance, 'About Stations');
    });

    it('explains the counting rule in neutral words', async () => {
      renderEvent(specialDetail);
      const note = await screen.findByRole('note');
      expect(note).toHaveTextContent(/^A special shoot counts as a Sunday shot/);
      expect(note.textContent).not.toMatch(/\b(he|she|his|her)\b/i);
    });

    it('shows shooters, targets and stations, and no median, top score or difficulty', async () => {
      renderEvent(specialDetail);
      const glance = await screen.findByRole('region', { name: 'This Sunday' });
      for (const [label, value] of [
        ['Shooters', '3'],
        ['Targets', '60'],
        ['Stations', '10'],
      ] as const) {
        expect(within(glance).getByText(label).closest('div')?.parentElement).toHaveTextContent(
          value,
        );
      }
      for (const label of ['Median', 'Top score', 'Difficulty', 'Head count']) {
        expect(within(glance).queryByText(label)).not.toBeInTheDocument();
      }
      for (const stat of ['Shooters', 'Targets']) await expectExplainer(glance, `About ${stat}`);
      await expectExplainer(glance, 'About Targets', { read: true });
    });

    it(
      'lists the results out of 60, best first, and draws the station grid',
      async () => {
        renderEvent(specialDetail);
        const results = await screen.findByRole('table', { name: 'Results' });
        expect(within(results).getByRole('columnheader', { name: 'Score (of 60)' })).toBeVisible();
        expect(
          within(results).queryByRole('columnheader', { name: 'Rank' }),
        ).not.toBeInTheDocument();
        expect(within(results).getAllByRole('row')).toHaveLength(4);
        expect(
          await screen.findByRole(
            'img',
            { name: 'Station hits heatmap for Sep 20, 2026' },
            LAZY_CHART,
          ),
        ).toBeInTheDocument();
      },
      LAZY_TEST_TIMEOUT,
    );

    it('keeps the weather but has no comparison with the previous Sunday', async () => {
      renderEvent(specialDetail);
      await screen.findByRole('table', { name: 'Results' });
      expect(screen.queryByRole('region', { name: 'vs previous Sunday' })).not.toBeInTheDocument();
      expect(screen.getByText('No weather recorded for this Sunday')).toBeInTheDocument();
      // First-timers are told by Sunday insights (Plan 12), which a special Sunday does not get (Decision 12).
      expect(screen.queryByRole('region', { name: 'Notables' })).not.toBeInTheDocument();
      expectUnbrokenOutline();
    });

    it('a special Sunday without a name or a station sheet still reads cleanly', async () => {
      renderEvent({ ...specialDetail, label: null, stations: null });
      expect(await screen.findByText('Special · 60 targets')).toBeInTheDocument();
      const glance = screen.getByRole('region', { name: 'This Sunday' });
      expect(within(glance).getByText('Stations').closest('div')?.parentElement).toHaveTextContent(
        '—',
      );
      expect(screen.queryByText('Station hits')).not.toBeInTheDocument();
    });
  });
});
