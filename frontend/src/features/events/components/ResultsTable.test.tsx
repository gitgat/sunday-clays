import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import type { EventResult } from '../api';
import { highlightedShooters, ResultsTable } from './ResultsTable';

function result(over: Partial<EventResult>): EventResult {
  return {
    round_id: 1,
    shooter_id: 1,
    display_name: 'Shooter, A',
    name_key: 'shooter a',
    shooter_status: 'member',
    ordinal: 1,
    score: 40,
    adjusted: 0,
    event_rank: 1,
    is_best_round: true,
    percentile: 1,
    expected: null,
    residual: null,
    mu_before: null,
    mu_after: null,
    rating_delta: null,
    gauge_class: null,
    ...over,
  };
}

function cells(rowIndex: number): string[] {
  const row = screen.getAllByRole('row')[rowIndex];
  if (!row) throw new Error(`no row ${rowIndex}`);
  return within(row)
    .getAllByRole('cell')
    .map((c) => c.textContent ?? '');
}

describe('ResultsTable', () => {
  it('tied best rounds share a T-rank', () => {
    renderWithProviders(
      <ResultsTable
        results={[
          result({
            round_id: 3,
            shooter_id: 3,
            display_name: 'Grimsby, Gregor',
            score: 48,
            event_rank: 3,
          }),
          result({
            round_id: 1,
            shooter_id: 1,
            display_name: 'Finnegan, Stanton',
            score: 49,
            event_rank: 1,
          }),
          result({
            round_id: 2,
            shooter_id: 2,
            display_name: 'Stockton, Ethan',
            score: 49,
            event_rank: 1,
          }),
        ]}
      />,
    );
    expect(cells(1).slice(0, 3)).toEqual(['T1', 'Finnegan, Stanton', '49']);
    expect(cells(2).slice(0, 3)).toEqual(['T1', 'Stockton, Ethan', '49']);
    expect(cells(3).slice(0, 3)).toEqual(['3', 'Grimsby, Gregor', '48']);
  });

  it('extra round shows no rank and an R2 badge', () => {
    renderWithProviders(
      <ResultsTable
        results={[
          result({
            round_id: 11,
            display_name: 'Nickerson, Neal',
            ordinal: 2,
            is_best_round: false,
            event_rank: null,
          }),
          result({ round_id: 10, display_name: 'Nickerson, Neal', ordinal: 1, event_rank: 9 }),
        ]}
      />,
    );
    expect(cells(1).slice(0, 2)).toEqual(['9', 'Nickerson, Neal']);
    expect(cells(2).slice(0, 2)).toEqual(['—', 'Nickerson, NealR2']);
  });

  it('shows the rating change only on the best round and adjusted scores with a sign', () => {
    renderWithProviders(
      <ResultsTable
        results={[
          result({
            round_id: 10,
            ordinal: 1,
            adjusted: 6,
            event_rank: 9,
            mu_before: 30.1,
            mu_after: 30.9,
            rating_delta: 0.8,
          }),
          result({
            round_id: 11,
            ordinal: 2,
            adjusted: -2,
            score: 32,
            is_best_round: false,
            event_rank: null,
            mu_before: 30.1,
            mu_after: 30.9,
            rating_delta: 0.8,
          }),
          result({
            round_id: 12,
            shooter_id: 2,
            display_name: 'Newcomer, Nate',
            score: 20,
            adjusted: -14,
            event_rank: 12,
            rating_delta: null,
          }),
        ]}
      />,
    );
    expect(cells(1).slice(3)).toEqual(['+6.0', '+0.8']);
    expect(cells(2).slice(3)).toEqual(['−2.0', '—']);
    expect(cells(3).slice(3)).toEqual(['−14.0', '—']);
  });

  it('shows the column headings in plain words', () => {
    renderWithProviders(<ResultsTable results={[result({})]} />);
    expect(screen.getByRole('columnheader', { name: 'Vs middle score' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Rating change' })).toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: 'Adj.' })).not.toBeInTheDocument();
  });

  it('shows a dash, not 0.0, for the rating change of a partial-results Sunday', () => {
    renderWithProviders(
      <ResultsTable
        complete={false}
        results={[
          result({ mu_before: 30.1, mu_after: 30.1, rating_delta: 0 }),
          result({ round_id: 2, shooter_id: 2, is_best_round: false, rating_delta: 0 }),
        ]}
      />,
    );
    expect(cells(1).at(-1)).toBe('—');
    expect(cells(2).at(-1)).toBe('—');
  });

  it('still shows a real 0.0 rating change on a full-results Sunday', () => {
    renderWithProviders(<ResultsTable results={[result({ rating_delta: 0 })]} />);
    expect(cells(1).at(-1)).toBe('0.0');
  });

  it('links each shooter to their profile', () => {
    renderWithProviders(
      <ResultsTable results={[result({ shooter_id: 3, display_name: 'Hadley, Ike' })]} />,
    );
    expect(screen.getByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/3',
    );
  });

  it('keeps the global round-type filter on profile links', () => {
    renderWithProviders(
      <ResultsTable results={[result({ shooter_id: 3, display_name: 'Hadley, Ike' })]} />,
      {
        route: '/events/2026-09-13?rt=sporting',
      },
    );
    expect(screen.getByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/3?rt=sporting',
    );
  });

  it('shooter links are visibly links with a 44 px tap target (C10)', () => {
    renderWithProviders(<ResultsTable results={[result({ display_name: 'Ng, Al' })]} />);
    // Underlined without hover (touch screens never hover); jsdom has no layout, so the size
    // classes stand in for the e2e measurement in events.spec.ts.
    expect(screen.getByRole('link', { name: 'Ng, Al' })).toHaveClass(
      'underline',
      'min-h-11',
      'min-w-11',
    );
  });
});

describe('ResultsTable highlight (Plan 12)', () => {
  it('marks the rows of the shooters an insight points to', () => {
    renderWithProviders(
      <ResultsTable
        results={[
          result({ round_id: 1, shooter_id: 3, display_name: 'Hadley, Ike', score: 44 }),
          result({ round_id: 2, shooter_id: 4, display_name: 'Bee, Bob', score: 40 }),
        ]}
        highlight={highlightedShooters(['s:3', '2026-09-27'])}
      />,
    );
    const marked = screen
      .getAllByRole('row')
      .filter((row) => row.getAttribute('aria-current') === 'true');
    expect(marked).toHaveLength(1);
    expect(marked[0]).toHaveTextContent('Hadley, Ike');
  });
});
