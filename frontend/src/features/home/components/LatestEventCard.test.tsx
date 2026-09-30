import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { expectExplainer } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { homeMeta, latestEvent } from '../mocks';
import { attendanceText, LatestEventCard, winners } from './LatestEventCard';

const fail = () =>
  HttpResponse.json(
    { error: { code: 'internal', message: 'Internal server error' } },
    { status: 500 },
  );

describe('winners', () => {
  it('lists every best round ranked first, alphabetically', () => {
    expect(winners(latestEvent.results)).toEqual(['Finnegan, Stanton', 'Stockton, Ethan']);
  });
});

describe('attendanceText', () => {
  it.each([
    [21, 'Attendance only — 21 shooters, no scores recorded'],
    [null, 'No scores recorded'],
  ])('%s → %s', (headCount, want) => {
    expect(attendanceText(headCount)).toBe(want);
  });
});

describe('LatestEventCard', () => {
  it('shows the latest event with tied winners and its numbers', async () => {
    server.use(
      http.get('*/api/meta', () => HttpResponse.json(homeMeta)),
      http.get('*/api/events/:date', () => HttpResponse.json(latestEvent)),
    );
    renderWithProviders(<LatestEventCard />);
    expect(await screen.findByRole('link', { name: 'Sep 27, 2026' })).toHaveAttribute(
      'href',
      '/events/2026-09-27',
    );
    expect(
      screen.getByText('Winners: Finnegan, Stanton & Stockton, Ethan — 49'),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Full results' })).toHaveAttribute(
      'href',
      '/events/2026-09-27',
    );
  });

  it('is titled Latest Sunday and explains each number', async () => {
    server.use(
      http.get('*/api/meta', () => HttpResponse.json(homeMeta)),
      http.get('*/api/events/:date', () => HttpResponse.json(latestEvent)),
    );
    renderWithProviders(<LatestEventCard />);
    const card = await screen.findByRole('region', { name: 'Latest Sunday' });
    await screen.findByText('Winners: Finnegan, Stanton & Stockton, Ethan — 49');
    for (const stat of ['Shooters', 'Median', 'Top score']) {
      await expectExplainer(card, `About ${stat}`);
    }
  });

  it('keeps the global round-type filter on its event links', async () => {
    server.use(
      http.get('*/api/meta', () => HttpResponse.json(homeMeta)),
      http.get('*/api/events/:date', () => HttpResponse.json(latestEvent)),
    );
    renderWithProviders(<LatestEventCard />, { route: '/?rt=super_sporting' });
    expect(await screen.findByRole('link', { name: 'Sep 27, 2026' })).toHaveAttribute(
      'href',
      '/events/2026-09-27?rt=super_sporting',
    );
    expect(screen.getByRole('link', { name: 'Full results' })).toHaveAttribute(
      'href',
      '/events/2026-09-27?rt=super_sporting',
    );
  });

  it('says Winner for a single winner', async () => {
    server.use(
      http.get('*/api/meta', () => HttpResponse.json(homeMeta)),
      http.get('*/api/events/:date', () =>
        HttpResponse.json({ ...latestEvent, results: latestEvent.results.slice(1) }),
      ),
    );
    renderWithProviders(<LatestEventCard />);
    expect(await screen.findByText('Winner: Stockton, Ethan — 49')).toBeInTheDocument();
  });

  it('leaves the winner line out when no best round is ranked first', async () => {
    server.use(
      http.get('*/api/meta', () => HttpResponse.json(homeMeta)),
      http.get('*/api/events/:date', () =>
        HttpResponse.json({
          ...latestEvent,
          results: latestEvent.results.map((r) => ({ ...r, event_rank: null })),
        }),
      ),
    );
    renderWithProviders(<LatestEventCard />);
    expect(await screen.findByRole('link', { name: 'Sep 27, 2026' })).toBeInTheDocument();
    expect(screen.queryByText(/Winners?:/)).not.toBeInTheDocument();
    // The stats row still carries the top score.
    expect(screen.getByText('Top score')).toBeInTheDocument();
    expect(screen.getAllByText('49')).toHaveLength(1);
  });

  it('shows an attendance-only latest event', async () => {
    server.use(
      http.get('*/api/meta', () => HttpResponse.json(homeMeta)),
      http.get('*/api/events/:date', () =>
        HttpResponse.json({
          ...latestEvent,
          has_scores: false,
          head_count: 21,
          results: [],
          median: null,
          top_score: null,
        }),
      ),
    );
    renderWithProviders(<LatestEventCard />);
    expect(
      await screen.findByText('Attendance only — 21 shooters, no scores recorded'),
    ).toBeInTheDocument();
    // It points at the latest Sunday that has full results instead of a "Full results" link here.
    expect(
      screen.getByRole('link', { name: /^Latest full results: \w{3} \d{1,2}, 20\d\d$/ }),
    ).toHaveAttribute('href', `/events/${homeMeta.last_score_date}`);
    expect(screen.queryByRole('link', { name: 'Full results' })).not.toBeInTheDocument();
  });

  it('says it is not affected by the time filter, and dates the Sunday it shows', async () => {
    server.use(
      http.get('*/api/meta', () => HttpResponse.json(homeMeta)),
      http.get('*/api/events/:date', () => HttpResponse.json(latestEvent)),
    );
    renderWithProviders(<LatestEventCard />, { route: '/?w=3m' });
    expect(await screen.findByRole('link', { name: 'Sep 27, 2026' })).toBeInTheDocument();
    expect(screen.getByText('Not affected by the time filter')).toBeVisible();
  });

  it('says no events yet before any import', async () => {
    server.use(
      http.get('*/api/meta', () =>
        HttpResponse.json({
          ...homeMeta,
          first_event_date: null,
          last_event_date: null,
          first_score_date: null,
          last_score_date: null,
        }),
      ),
    );
    renderWithProviders(<LatestEventCard />);
    expect(await screen.findByText('No Sundays yet')).toBeInTheDocument();
  });

  it('shows a load failure when meta fails', async () => {
    server.use(http.get('*/api/meta', fail));
    renderWithProviders(<LatestEventCard />);
    expect(await screen.findByText("Couldn't load the latest Sunday")).toBeInTheDocument();
  });

  it('shows a load failure when the event fails', async () => {
    server.use(
      http.get('*/api/meta', () => HttpResponse.json(homeMeta)),
      http.get('*/api/events/:date', fail),
    );
    renderWithProviders(<LatestEventCard />);
    expect(await screen.findByText("Couldn't load the latest Sunday")).toBeInTheDocument();
  });
});
