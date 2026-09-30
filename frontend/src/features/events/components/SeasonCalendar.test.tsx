import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import type { EventSummary } from '../api';
import { eventSummaries } from '../mocks';
import { SeasonCalendar, sundaysOfYear } from './SeasonCalendar';

describe('sundaysOfYear', () => {
  it('lists the 52 Sundays of 2026', () => {
    const days = sundaysOfYear(2026);
    expect(days).toHaveLength(52);
    expect(days[0]).toBe('2026-01-04');
    expect(days.at(-1)).toBe('2026-12-27');
  });

  it('starts on January 1 when it is a Sunday', () => {
    expect(sundaysOfYear(2023)[0]).toBe('2023-01-01');
  });
});

// Every Plan 06 EventSummaryOut field is required; these dates have no scores, so no metrics and no winners.
function unscored(event_date: string, head_count: number | null): EventSummary {
  return {
    event_date,
    round_type: 'sporting',
    round_type_source: 'none',
    head_count,
    has_scores: false,
    has_stations: false,
    results_complete: false,
    n_rounds: 0,
    n_shooters: 0,
    median: null,
    top_score: null,
    difficulty: null,
    condition: null,
    winners: [],
  };
}

describe('SeasonCalendar', () => {
  it('links each event date and labels scored, attendance-only and score-less dates', () => {
    const events: EventSummary[] = [
      unscored('2019-01-06', null),
      unscored('2019-01-14', 9),
      unscored('2018-12-30', 7),
    ];
    renderWithProviders(<SeasonCalendar year={2019} events={events} />);
    const calendar = screen.getByRole('region', { name: 'Calendar 2019' });
    const links = within(calendar).getAllByRole('link');
    expect(links.map((l) => l.getAttribute('aria-label'))).toEqual([
      'Jan 6, 2019 — no scores',
      'Jan 14, 2019 — attendance only, 9 shooters',
    ]);
    expect(links[1]).toHaveAttribute('href', '/events/2019-01-14');
  });

  it('labels scored events with their shooter count', () => {
    renderWithProviders(
      <SeasonCalendar
        year={2026}
        events={eventSummaries.filter((e) => e.event_date.startsWith('2026'))}
      />,
    );
    expect(screen.getByRole('link', { name: 'Sep 13, 2026 — 13 shooters' })).toBeInTheDocument();
    expect(screen.getAllByRole('link')).toHaveLength(4);
  });

  it('has a legend for its scored, score-less and empty cells', () => {
    renderWithProviders(
      <SeasonCalendar
        year={2026}
        events={eventSummaries.filter((e) => e.event_date.startsWith('2026'))}
      />,
    );
    const calendar = screen.getByRole('region', { name: 'Calendar 2026' });
    const legend = within(calendar).getByRole('list', { name: 'Calendar legend' });
    const items = within(legend).getAllByRole('listitem');
    // Each swatch is a decorative (aria-hidden) sample cell; the text after it names the state.
    expect(items.map((li) => li.lastChild?.textContent)).toEqual([
      'Scored',
      'No scores',
      'Other round type',
      'No Sunday on file',
    ]);
    for (const li of items) expect(li.firstElementChild).toHaveAttribute('aria-hidden', 'true');
  });

  it('marks Sundays the round-type filter hides as "Other round type", not absent', () => {
    renderWithProviders(
      <SeasonCalendar
        year={2019}
        events={[unscored('2019-01-06', 9)]}
        otherRoundType={['2019-01-13']}
      />,
    );
    const calendar = screen.getByRole('region', { name: 'Calendar 2019' });
    // Hidden by the filter: a labelled, non-link cell. Absent (Jan 20): the faded, aria-hidden one.
    const hidden = within(calendar).getByRole('img', { name: 'Jan 13, 2019 — other round type' });
    expect(hidden).toHaveTextContent('13');
    expect(within(calendar).queryByRole('link', { name: /Jan 13/ })).not.toBeInTheDocument();
    expect(within(calendar).getAllByRole('img')).toHaveLength(1);
  });

  it('keeps the global round-type filter on date links', () => {
    renderWithProviders(<SeasonCalendar year={2019} events={[unscored('2019-01-14', 9)]} />, {
      route: '/events?year=2019&rt=super_sporting',
    });
    expect(
      screen.getByRole('link', { name: 'Jan 14, 2019 — attendance only, 9 shooters' }),
    ).toHaveAttribute('href', '/events/2019-01-14?rt=super_sporting');
  });
});
