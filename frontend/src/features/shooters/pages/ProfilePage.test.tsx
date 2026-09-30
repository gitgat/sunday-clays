import { act, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it } from 'vitest';
import { clearMe } from '../../../lib/me';
import { expectChartControls } from '../../../test/charts';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import {
  gilchristDetail,
  clubDistribution,
  hadleyDetail,
  hadleyInsights,
  hadleyRating,
  hadleyRounds,
  hadleySplitsByYear,
} from '../mocks';
import type { ProfileSection } from '../sections';
import { ProfilePage } from './ProfilePage';

const seen: URLSearchParams[] = [];

function renderProfile(route: string, sections: ProfileSection[] = []) {
  return renderWithProviders(
    <Routes>
      <Route path="/shooters/:id" element={<ProfilePage sections={sections} />} />
    </Routes>,
    { route },
  );
}

describe('ProfilePage', () => {
  beforeEach(() => {
    clearMe();
    seen.length = 0;
    server.use(
      http.get('*/api/shooters/:id', ({ params, request }) => {
        seen.push(new URL(request.url).searchParams);
        if (params.id === '3') return HttpResponse.json(hadleyDetail);
        if (params.id === '41') return HttpResponse.json(gilchristDetail);
        return HttpResponse.json(
          { error: { code: 'not_found', message: 'No such shooter' } },
          { status: 404 },
        );
      }),
      http.get('*/api/shooters/:id/insights', () => HttpResponse.json(hadleyInsights)),
      http.get('*/api/shooters/:id/rounds', () => HttpResponse.json(hadleyRounds)),
      http.get('*/api/shooters/:id/rating', () => HttpResponse.json(hadleyRating)),
      http.get('*/api/shooters/:id/splits', () => HttpResponse.json(hadleySplitsByYear)),
      http.get('*/api/club/distribution', () => HttpResponse.json(clubDistribution)),
    );
  });

  it('labels the hero counts in Sundays and explains the stats', async () => {
    renderProfile('/shooters/3');
    const name = await screen.findByRole('heading', { level: 1, name: 'Hadley, Ike' });
    const hero = within(name.closest('header') as HTMLElement);
    expect(hero.getByText('Sundays')).toBeInTheDocument();
    expect(hero.queryByText('Events')).toBeNull();
    for (const stat of ['Rounds', 'Sundays', 'Average', 'Median']) {
      expect(hero.getByRole('button', { name: `About ${stat}` })).toBeInTheDocument();
    }
  });

  it('shows the hero stats, the odometer and the insights card', async () => {
    renderProfile('/shooters/3');
    const name = await screen.findByRole('heading', { level: 1, name: 'Hadley, Ike' });
    // Scoped to the hero: once Task 3 adds charts, their data tables may repeat numbers such as 35.3.
    const hero = within(name.closest('header') as HTMLElement);
    expect(hero.getByText('Member')).toBeInTheDocument();
    expect(hero.getByText('Jan 5, 2020 – Sep 27, 2026')).toBeInTheDocument();
    expect(hero.getByText('35.3')).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Lifetime odometer' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: "That's me" })).toBeInTheDocument();
    expect(await screen.findByText('Hot (+3.4)')).toBeInTheDocument();
    expect(screen.queryByText('In memoriam')).not.toBeInTheDocument();
  });

  it(
    'every data chart exposes Table and CSV controls',
    async () => {
      renderProfile('/shooters/3');
      await screen.findByRole('heading', { level: 1, name: 'Hadley, Ike' });
      // ECharts loads on demand, after the shell and the chart data.
      await waitFor(() => expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(7), {
        timeout: LAZY_CHART.timeout,
      });
      expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(7);
      const charts = screen.getAllByRole('img');
      expect(charts).toHaveLength(7);
      for (const chart of charts) {
        const region = chart.closest('section');
        expect(region, 'a chart outside ChartFrame/ChartCard').not.toBeNull();
        expectChartControls(region as HTMLElement);
      }
      expect(screen.getByRole('table', { name: 'Personal bests' })).toBeInTheDocument();
    },
    LAZY_TEST_TIMEOUT,
  );

  it('shows the memorial marker for a deceased shooter, with no That’s me or milestone projection', async () => {
    server.use(
      http.get('*/api/shooters/:id/insights', () =>
        HttpResponse.json({
          ...hadleyInsights,
          shooter_id: 41,
          milestone: {
            next_events: 25,
            events_to_go: 14,
            weekly_rate: 0.2,
            projected_date: '2027-10-03',
          },
        }),
      ),
    );
    renderProfile('/shooters/41');
    const name = await screen.findByRole('heading', { level: 1, name: 'Gilchrist, Melvin' });
    expect(
      within(name.closest('header') as HTMLElement).getByText('In memoriam'),
    ).toBeInTheDocument();
    const insights = screen.getByRole('region', { name: 'Stats' });
    expect(await within(insights).findByText('Hot (+3.4)')).toBeInTheDocument();
    expect(within(insights).queryByText('Next milestone')).not.toBeInTheDocument();
    expect(screen.queryByText(/to go/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: "That's me" })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'This is you' })).not.toBeInTheDocument();
  });

  it('still shows the lifetime numbers when /api/meta fails, and says the window could not load', async () => {
    server.use(
      http.get('*/api/meta', () =>
        HttpResponse.json({ error: { code: 'boom', message: 'down' } }, { status: 500 }),
      ),
    );
    renderProfile('/shooters/3');
    const name = await screen.findByRole('heading', { level: 1, name: 'Hadley, Ike' });
    const hero = within(name.closest('header') as HTMLElement);
    expect(hero.getByText('35.3')).toBeInTheDocument();
    expect(await hero.findByText("Couldn't load the time window.")).toBeInTheDocument();
    expect(seen.at(-1)?.has('since')).toBe(false);
  });

  it('hides the windowed row for the All window, which would repeat Lifetime', async () => {
    renderProfile('/shooters/3?w=all');
    const name = await screen.findByRole('heading', { level: 1, name: 'Hadley, Ike' });
    const hero = within(name.closest('header') as HTMLElement);
    expect(hero.getByRole('heading', { name: 'Lifetime' })).toBeInTheDocument();
    expect(hero.queryByRole('heading', { name: /^In / })).toBeNull();
  });

  it('appends the global round-type filter to the detail request', async () => {
    renderProfile('/shooters/3?rt=super_sporting');
    await screen.findByRole('heading', { level: 1, name: 'Hadley, Ike' });
    expect(seen.at(-1)?.getAll('round_type')).toEqual(['super_sporting']);
  });

  it(
    'renders registered profile sections with the shooter id',
    async () => {
      renderProfile('/shooters/3', [
        {
          id: 'trophies',
          title: 'Trophy case',
          order: 10,
          Component: ({ shooterId }) => <p>trophies of {shooterId}</p>,
        },
      ]);
      // D5: the section renders inside a Card region named by its title, below the insights card.
      const section = await screen.findByRole('region', { name: 'Trophy case' });
      await waitFor(() => expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(7), {
        timeout: LAZY_CHART.timeout,
      });
      expect(within(section).getByText('trophies of 3')).toBeInTheDocument();
      const regions = screen.getAllByRole('region').map((r) => r.getAttribute('aria-labelledby'));
      const titleOf = (id: string | null) =>
        id === null ? null : document.getElementById(id)?.textContent;
      expect(regions.map(titleOf)).toEqual([
        'Stats',
        'Rating',
        'Scores over time',
        'Finishes',
        'Score distribution vs club',
        'Learning curve vs club',
        'Splits by Year',
        'Tough days',
        'Attendance calendar 2026',
        'Personal bests',
        'Trophy case',
      ]);
    },
    LAZY_TEST_TIMEOUT,
  );

  it('renders top sections above the stats card', async () => {
    renderProfile('/shooters/3', [
      {
        id: 'first',
        title: 'Up top',
        order: 1,
        placement: 'top',
        Component: ({ shooterId }) => <p>top for {shooterId}</p>,
      },
    ]);
    const top = await screen.findByRole('region', { name: 'Up top' });
    const stats = screen.getByRole('region', { name: 'Stats' });
    expect(top.compareDocumentPosition(stats) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(top).getByText('top for 3')).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(7), {
      timeout: LAZY_CHART.timeout,
    });
  });

  it('an unknown id says the shooter was not found', async () => {
    renderProfile('/shooters/999');
    expect(await screen.findByText('Shooter not found')).toBeInTheDocument();
    expect(screen.getByText('They may have been merged into another name.')).toBeInTheDocument();
  });

  it('adds a windowed row above the lifetime numbers and asks for the window', async () => {
    server.use(
      http.get('*/api/shooters/:id', ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return HttpResponse.json({
          ...hadleyDetail,
          window_stats: {
            ...hadleyDetail.stats,
            n_rounds: 6,
            n_events: 5,
            avg_score: 36.5,
            best_score: 44,
          },
        });
      }),
    );
    renderProfile('/shooters/3');
    const name = await screen.findByRole('heading', { level: 1, name: 'Hadley, Ike' });
    const hero = within(name.closest('header') as HTMLElement);
    expect(
      hero.getByRole('heading', { name: 'In the last 8 weeks (Aug 3 – Sep 27)' }),
    ).toBeVisible();
    expect(hero.getByRole('heading', { name: 'Lifetime' })).toBeVisible();
    expect(hero.getByText('36.5')).toBeVisible();
    expect(hero.getByText('5 Sundays')).toBeVisible();
    for (const stat of ['Rounds', 'Average', 'Best']) {
      // One in the window row, one under Lifetime.
      expect(hero.getAllByRole('button', { name: `About ${stat}` })).toHaveLength(2);
    }
    expect(seen.at(-1)?.get('since')).toBe('2026-08-03');
    expect(seen.at(-1)?.get('as_of')).toBe('2026-09-27');
  });

  it('says so, naming the period, when the window holds no rounds', async () => {
    server.use(
      http.get('*/api/shooters/:id', () =>
        HttpResponse.json({
          ...hadleyDetail,
          window_stats: { ...hadleyDetail.stats, n_rounds: 0, avg_score: null, best_score: null },
        }),
      ),
    );
    renderProfile('/shooters/3?w=3m');
    expect(
      await screen.findByText(
        'No rounds in the last 3 months (Jun 28 – Sep 27). Pick 12M or All in the time filter above to see more.',
      ),
    ).toBeVisible();
    // Lifetime still shows.
    expect(screen.getByRole('heading', { name: 'Lifetime' })).toBeVisible();
  });

  it('keeps the page on screen while a new window loads', async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get('*/api/shooters/:id', async ({ request }) => {
        if (new URL(request.url).searchParams.get('since') === '2025-09-28') await gate;
        return HttpResponse.json(hadleyDetail);
      }),
    );
    const { router } = renderProfile('/shooters/3');
    await screen.findByRole('heading', { level: 1, name: 'Hadley, Ike' });
    await act(() => router.navigate('/shooters/3?w=12m'));
    // The 12M answer is held back: the profile stays, no skeleton in its place.
    expect(screen.getByRole('heading', { level: 1, name: 'Hadley, Ike' })).toBeVisible();
    release();
    expect(await screen.findByRole('heading', { name: /In the last 12 months/ })).toBeVisible();
  });

  it('a malformed id says the shooter was not found without calling the API', async () => {
    renderProfile('/shooters/abc');
    expect(await screen.findByText('Shooter not found')).toBeInTheDocument();
    expect(seen).toHaveLength(0);
  });

  it('a server error shows a load failure', async () => {
    server.use(
      http.get('*/api/shooters/:id', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    renderProfile('/shooters/3');
    expect(await screen.findByText("Couldn't load this shooter")).toBeInTheDocument();
  });
});
