import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { gilchristDetail, hadleyDetail } from '../mocks';
import { odometerItems, OdometerStrip } from './OdometerStrip';

describe('odometerItems', () => {
  it('formats every C12 odometer field, computing the hit rate from broken / thrown', () => {
    expect(odometerItems(gilchristDetail.odometer)).toEqual([
      { label: 'Clays thrown', value: '550' },
      { label: 'Clays broken', value: '409' },
      { label: 'Hit rate', value: '74.4%' },
      { label: 'Rounds', value: '11' },
      { label: 'Sundays', value: '11' },
      { label: 'Years active', value: '1' },
      { label: 'Current streak', value: '0' },
      { label: 'Longest streak', value: '6' },
      { label: 'Favorite month', value: 'September' },
      { label: 'Trophies', value: '0' },
    ]);
  });

  it('groups thousands and shows dashes when nothing has been thrown', () => {
    expect(odometerItems(hadleyDetail.odometer).slice(0, 2)).toEqual([
      { label: 'Clays thrown', value: '13,350' },
      { label: 'Clays broken', value: '9,427' },
    ]);
    const empty = odometerItems({
      ...gilchristDetail.odometer,
      clays_thrown: 0,
      clays_broken: 0,
      favorite_month: null,
    });
    expect(empty[2]).toEqual({ label: 'Hit rate', value: '—' });
    expect(empty[8]).toEqual({ label: 'Favorite month', value: '—' });
  });
});

describe('OdometerStrip', () => {
  it('renders a list named by its visible heading with one item per odometer field', () => {
    renderWithProviders(<OdometerStrip odometer={gilchristDetail.odometer} />);
    // Visible, not screen-reader only: the hero's Rounds/Events follow ?rt=, these are lifetime totals.
    const heading = screen.getByRole('heading', { level: 2, name: 'Lifetime odometer' });
    expect(heading).not.toHaveClass('sr-only');
    const list = screen.getByRole('list', { name: 'Lifetime odometer' });
    expect(list).toHaveAttribute('aria-labelledby', heading.id);
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(10);
    expect(items[0]).toHaveTextContent('Clays thrown550');
  });

  it('says it ignores the round-type filter and explains itself', async () => {
    renderWithProviders(<OdometerStrip odometer={gilchristDetail.odometer} />);
    expect(screen.getByText('All round types')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'About the odometer' }));
    expect(screen.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  });
});
