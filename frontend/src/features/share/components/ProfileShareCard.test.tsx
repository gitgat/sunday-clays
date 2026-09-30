import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { hadleyDetail } from '../../shooters/mocks';
import { ProfileShareCard } from './ProfileShareCard';

function value(label: string): string | null | undefined {
  return screen.getByText(label).nextElementSibling?.textContent;
}

describe('ProfileShareCard', () => {
  it('shows the overall personal best and the lifetime odometer', () => {
    render(<ProfileShareCard shooter={hadleyDetail} />);
    expect(screen.getByRole('heading', { name: 'Hadley, Ike' })).toBeInTheDocument();
    expect(value('Personal best')).toBe('45 (Sun, Apr 3, 2022)');
    expect(value('Clays broken')).toBe('9,427');
    expect(value('Rounds')).toBe('267');
    expect(value('Sundays')).toBe('267');
    expect(value('Years active')).toBe('7');
    expect(value('Longest streak')).toBe('31 Sundays');
    expect(screen.queryByText('In memory')).not.toBeInTheDocument();
  });

  it('marks shooters who have died and copes without a personal best', () => {
    render(<ProfileShareCard shooter={{ ...hadleyDetail, deceased: true, pbs: [] }} />);
    expect(screen.getByText('In memory')).toBeInTheDocument();
    expect(value('Personal best')).toBe('—');
  });

  it('says a streak of one in the singular', () => {
    render(
      <ProfileShareCard
        shooter={{ ...hadleyDetail, odometer: { ...hadleyDetail.odometer, longest_streak: 1 } }}
      />,
    );
    expect(value('Longest streak')).toBe('1 Sunday');
  });
});
