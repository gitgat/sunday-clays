import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import type { components } from '../../api/schema';
import { CoverageNote, ScopeLine, ShooterCoverageNote } from './CoverageNote';

type Coverage = components['schemas']['StationCoverageOut'];
type ShooterCoverage = components['schemas']['ShooterStationCoverageOut'];
const two: Coverage = {
  n_station_sundays: 2,
  first_date: '2026-09-06',
  last_date: '2026-09-13',
  n_scored_sundays: 311,
  latest_date: '2026-09-13',
};
const mine: ShooterCoverage = {
  n_rounds: 3,
  n_sundays: 2,
  first_date: '2026-09-06',
  last_date: '2026-09-13',
  latest_date: '2026-09-13',
};

function renderIn(ui: React.ReactNode, url = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('CoverageNote', () => {
  it('states the counts, the period and the date span it is given', () => {
    renderIn(<CoverageNote coverage={two} filtered={false} />);
    const note = screen.getByRole('note', { name: 'Station data coverage' });
    expect(note).toHaveTextContent(
      'Station scores cover 2 of 311 Sundays in the last 8 weeks (Sep 6, 2026 – Sep 13, 2026).',
    );
    expect(note).toHaveTextContent('Older station sheets weren’t kept');
    expect(note).not.toHaveTextContent('round types');
  });

  it('names the window it counts in', () => {
    renderIn(<CoverageNote coverage={two} filtered={false} />, '/?w=12m');
    expect(screen.getByRole('note')).toHaveTextContent('in the last 12 months');
    renderIn(<CoverageNote coverage={two} filtered={false} />, '/?w=all');
    expect(screen.getAllByRole('note')[1]).toHaveTextContent(
      'Station scores cover 2 of 311 Sundays so far',
    );
  });

  it('says "1 Sunday" and shows one date when there is a single Sunday', () => {
    renderIn(
      <CoverageNote
        coverage={{ ...two, n_station_sundays: 1, last_date: '2026-09-06', n_scored_sundays: 1 }}
        filtered={false}
      />,
    );
    expect(screen.getByRole('note')).toHaveTextContent(
      'Station scores cover 1 of 1 Sunday in the last 8 weeks (Sep 6, 2026).',
    );
  });

  it('drops the small-sample wording once station Sundays are a fair share of the history', () => {
    renderIn(<CoverageNote coverage={{ ...two, n_scored_sundays: 8 }} filtered={false} />);
    const note = screen.getByRole('note');
    expect(note).toHaveTextContent('Station scores cover 2 of 8 Sundays');
    expect(note).not.toHaveTextContent('small sample');
    expect(note).not.toHaveTextContent('Older station sheets');
  });

  it('says which Sundays the counts cover when a round-type filter is on', () => {
    renderIn(<CoverageNote coverage={two} filtered />);
    expect(screen.getByRole('note')).toHaveTextContent('Counts follow the round types you picked.');
  });

  it('renders nothing when there are no station Sundays', () => {
    const { container } = renderIn(
      <CoverageNote
        coverage={{ ...two, n_station_sundays: 0, first_date: null, last_date: null }}
        filtered={false}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe('ShooterCoverageNote', () => {
  it('describes the shooter’s own rounds, not the club’s', () => {
    renderIn(<ShooterCoverageNote coverage={mine} filtered={false} />);
    const note = screen.getByRole('note', { name: 'Station data coverage' });
    expect(note).toHaveTextContent(
      'Station scores for this shooter: 3 rounds on 2 Sundays in the last 8 weeks (Sep 6, 2026 – Sep 13, 2026).',
    );
    expect(note).not.toHaveTextContent('311');
    expect(note).not.toHaveTextContent('small sample');
  });

  it('says "1 round" and notes the round-type filter', () => {
    renderIn(
      <ShooterCoverageNote
        coverage={{ ...mine, n_rounds: 1, n_sundays: 1, last_date: '2026-09-06' }}
        filtered
      />,
    );
    const note = screen.getByRole('note');
    expect(note).toHaveTextContent('1 round on 1 Sunday in the last 8 weeks (Sep 6, 2026).');
    expect(note).toHaveTextContent('Counts follow the round types you picked.');
  });

  it('renders nothing without a station Sunday', () => {
    const { container } = renderIn(
      <ShooterCoverageNote coverage={{ ...mine, n_rounds: 0, n_sundays: 0 }} filtered={false} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe('ScopeLine', () => {
  it('names the setups, the window and its dates', async () => {
    renderIn(<ScopeLine era="current" />, '/?w=12m');
    expect(
      await screen.findByText('Current setups · Last 12 months · Sep 28, 2025 – Sep 27, 2026'),
    ).toBeInTheDocument();
  });
});
