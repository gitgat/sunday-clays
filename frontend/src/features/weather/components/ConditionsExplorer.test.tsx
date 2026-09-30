import { fireEvent, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { WEATHER_EVENTS } from '../mocks';
import { ConditionsExplorer } from './ConditionsExplorer';

function row(label: string): string[] {
  const term = screen.getByText(label);
  const cells: string[] = [];
  let next = term.nextElementSibling;
  while (next && next.tagName === 'DD') {
    cells.push(next.textContent ?? '');
    next = next.nextElementSibling;
  }
  return cells;
}

describe('ConditionsExplorer', () => {
  it('compares matching Sundays with all of them', () => {
    renderWithProviders(<ConditionsExplorer events={WEATHER_EVENTS} />);
    expect(screen.getByText('3 of 3 Sundays in the last 8 weeks match.')).toBeInTheDocument();
    expect(row('Mean field median')).toEqual(['37.3', '37.3']);
    expect(row('Mean difficulty')).toEqual(['−0.3', '−0.3']);
  });

  it('names the period on the All column and in the count, and says on record for all time', () => {
    const { unmount } = renderWithProviders(<ConditionsExplorer events={WEATHER_EVENTS} />, {
      route: '/?w=12m',
    });
    expect(screen.getByText('All, last 12 months')).toBeInTheDocument();
    expect(screen.getByText('3 of 3 Sundays in the last 12 months match.')).toBeInTheDocument();
    unmount();
    const { unmount: again } = renderWithProviders(<ConditionsExplorer events={WEATHER_EVENTS} />, {
      route: '/?w=all',
    });
    expect(screen.getByText('All time')).toBeInTheDocument();
    expect(screen.getByText('3 of 3 Sundays on record match.')).toBeInTheDocument();
    again();
    renderWithProviders(<ConditionsExplorer events={WEATHER_EVENTS} />, {
      route: '/?w=2026-08-01..2026-09-27',
    });
    expect(screen.getByText('All, Aug 1, 2026 – Sep 27, 2026')).toBeInTheDocument();
  });

  it('labels the open slider ends', () => {
    renderWithProviders(<ConditionsExplorer events={WEATHER_EVENTS} />);
    expect(screen.getByText('Coldest: 20°F or colder')).toBeInTheDocument();
    expect(screen.getByText('Warmest: 100°F or warmer')).toBeInTheDocument();
    expect(screen.getByText('Strongest gust: 40+ mph')).toBeInTheDocument();
  });

  it('filters by gust and rain and keeps the choice in the URL', () => {
    const { router } = renderWithProviders(<ConditionsExplorer events={WEATHER_EVENTS} />);
    fireEvent.change(screen.getByRole('slider', { name: /Strongest gust/ }), {
      target: { value: '10' },
    });
    expect(screen.getByText('1 of 3 Sundays in the last 8 weeks match.')).toBeInTheDocument();
    expect(row('Mean difficulty')).toEqual(['−0.5', '−0.3']);
    expect(router.state.location.search).toBe('?gust=10');
    fireEvent.change(screen.getByRole('combobox', { name: 'Rain' }), { target: { value: 'wet' } });
    expect(screen.getByText('0 of 3 Sundays in the last 8 weeks match.')).toBeInTheDocument();
    expect(row('Mean field median')).toEqual(['—', '37.3']);
  });

  it('reads the temperature range from the URL and never lets it cross', () => {
    renderWithProviders(<ConditionsExplorer events={WEATHER_EVENTS} />, {
      route: '/?temp=70..100',
    });
    expect(screen.getByText('1 of 3 Sundays in the last 8 weeks match.')).toBeInTheDocument();
    fireEvent.change(screen.getByRole('slider', { name: /Coldest/ }), { target: { value: '90' } });
    expect(screen.getByText('Coldest: 90°F')).toBeInTheDocument();
    fireEvent.change(screen.getByRole('slider', { name: /Warmest/ }), { target: { value: '40' } });
    expect(screen.getByText('Warmest: 90°F')).toBeInTheDocument();
    expect(screen.getByText('0 of 3 Sundays in the last 8 weeks match.')).toBeInTheDocument();
  });
});
