import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import type { EventSummary } from '../api';
import { eventSummaries } from '../mocks';
import { EventList, summaryLine } from './EventList';

function summary(over: Partial<EventSummary>): EventSummary {
  return {
    kind: 'regular',
    label: null,
    target_total: 50,
    event_date: '2026-09-13',
    round_type: 'super_sporting',
    round_type_source: 'stations',
    head_count: 13,
    has_scores: true,
    has_stations: true,
    results_complete: true,
    n_rounds: 13,
    n_shooters: 13,
    median: 34,
    top_score: 42,
    difficulty: 2.1,
    condition: null,
    winners: [{ shooter_id: 12, display_name: 'Nordquist, Sherman', score: 42 }],
    ...over,
  };
}

describe('summaryLine', () => {
  it.each([
    [summary({}), '13 shooters · Super Sporting · median 34 · top 42'],
    [summary({ median: null, top_score: null }), '13 shooters · Super Sporting'],
    [summary({ has_scores: false, head_count: 21 }), 'Attendance only · 21 shooters'],
    [summary({ has_scores: false, head_count: null }), 'No scores recorded'],
  ])('%# → %s', (event, want) => {
    expect(summaryLine(event)).toBe(want);
  });
});

describe('EventList', () => {
  it('lists events newest first with links to their pages', () => {
    renderWithProviders(
      <EventList
        year={2026}
        events={[...eventSummaries].reverse().filter((e) => e.event_date.startsWith('2026'))}
      />,
    );
    const items = within(screen.getByRole('list', { name: 'Sundays in 2026' })).getAllByRole(
      'listitem',
    );
    expect(items.map((i) => within(i).getByRole('link').getAttribute('href'))).toEqual([
      '/events/2026-09-27',
      '/events/2026-09-13',
      '/events/2026-09-06',
      '/events/2026-08-30',
    ]);
    expect(items[0]).toHaveTextContent('Sep 27, 2026');
  });

  it('keeps the global round-type filter on event links', () => {
    renderWithProviders(<EventList year={2026} events={[summary({})]} />, {
      route: '/events?rt=super_sporting',
    });
    expect(screen.getByRole('link')).toHaveAttribute(
      'href',
      '/events/2026-09-13?rt=super_sporting',
    );
  });
});
