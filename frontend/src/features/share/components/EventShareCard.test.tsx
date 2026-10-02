import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { attendanceOnlyDetail, eventDetail, specialDetail } from '../../events/mocks';
import type { EventDetail } from '../../events/api';
import { EventShareCard } from './EventShareCard';

type Result = EventDetail['results'][number];

const base = eventDetail.results[0] as Result;

function result(round_id: number, display_name: string, score: number, rank: number): Result {
  return { ...base, round_id, display_name, score, event_rank: rank, is_best_round: true };
}

const many: EventDetail = {
  ...eventDetail,
  results: [
    result(9, 'Crenshaw, Noel', 37, 4),
    result(1, 'Nordquist, Sherman', 42, 1),
    result(8, 'Kingsley, Teddy', 37, 4),
    result(2, 'Abernathy, Preston', 41, 2),
    result(6, 'McGinnis, Alvin', 36, 6),
    result(3, 'Kolmanov, Dmitri', 39, 3),
    { ...result(7, 'Kolmanov, Dmitri', 30, 9), is_best_round: false },
  ],
};

/** Seven special results whose score order differs from alphabetical order (invented names). */
function sevenSpecial(scores: number[]): EventDetail {
  const names = [
    'Abbott, Ann',
    'Bishop, Bo',
    'Cole, Cy',
    'Dunn, Di',
    'Egan, Ed',
    'Fox, Flo',
    'Gray, Gus',
  ];
  return {
    ...specialDetail,
    label: 'Flurry',
    target_total: 75,
    n_shooters: 7,
    results: names.map((n, i) => ({
      ...(specialDetail.results[0] as EventDetail['results'][number]),
      round_id: 100 + i,
      display_name: n,
      score: scores[i] as number,
    })),
  };
}

describe('EventShareCard', () => {
  it('shows the day, round type and the top five best rounds by rank', () => {
    render(<EventShareCard event={many} />);
    expect(screen.getByRole('heading', { name: 'Sun, Sep 13, 2026' })).toBeInTheDocument();
    expect(screen.getByText('Super Sporting · 13 shooters · median 34')).toBeInTheDocument();
    const rows = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(rows.map((r) => r.textContent)).toEqual([
      '1. Nordquist, Sherman42',
      '2. Abernathy, Preston41',
      '3. Kolmanov, Dmitri39',
      '4. Crenshaw, Noel37',
      '4. Kingsley, Teddy37',
    ]);
  });

  it('omits a missing median', () => {
    render(<EventShareCard event={{ ...many, median: null }} />);
    expect(screen.getByText('Super Sporting · 13 shooters')).toBeInTheDocument();
  });

  it('describes Sundays without scores', () => {
    const { rerender } = render(<EventShareCard event={attendanceOnlyDetail} />);
    expect(
      screen.getByText('Attendance only: 7 shooters, no scores recorded.'),
    ).toBeInTheDocument();
    rerender(<EventShareCard event={{ ...attendanceOnlyDetail, head_count: null }} />);
    expect(screen.getByText('No scores recorded.')).toBeInTheDocument();
  });

  it('a special Sunday shows its label, total and the top five by score, never Sporting', () => {
    render(<EventShareCard event={sevenSpecial([40, 70, 55, 72, 30, 71, 55])} />);
    expect(screen.getByText('Flurry · Special · 75 targets · 7 shooters')).toBeInTheDocument();
    expect(screen.queryByText(/Sporting/)).not.toBeInTheDocument();
    const rows = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(rows.map((r) => r.textContent)).toEqual([
      'Dunn, Di72 of 75',
      'Fox, Flo71 of 75',
      'Bishop, Bo70 of 75',
      'Cole, Cy55 of 75',
      'Gray, Gus55 of 75',
    ]);
  });

  it('a special Sunday without a name reads Special · N targets', () => {
    render(<EventShareCard event={{ ...specialDetail, label: null, target_total: 75 }} />);
    expect(screen.getByText('Special · 75 targets · 3 shooters')).toBeInTheDocument();
  });
});
