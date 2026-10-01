import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { insightFixture } from '../mocks';
import { MoreInsights } from './MoreInsights';

describe('MoreInsights', () => {
  it('groups the rest by family behind a closed "More insights" disclosure', async () => {
    const { user } = renderWithProviders(
      <MoreInsights
        items={[
          insightFixture({ key: 'a', family: 'streak' }),
          insightFixture({ key: 'b', family: 'milestone' }),
          insightFixture({ key: 'c', family: 'streak' }),
        ]}
        total={40}
      />,
    );
    const summary = screen.getByText('More insights (40)');
    expect(screen.queryByRole('region', { name: 'Streaks' })).not.toBeVisible();
    await user.click(summary);
    const streaks = screen.getByRole('region', { name: 'Streaks' });
    expect(within(streaks).getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByText('Showing 3 of 40.')).toBeInTheDocument();
  });

  it('names a family it does not know as it is and reads own cards in the second person', async () => {
    const { user } = renderWithProviders(
      <MoreInsights
        items={[insightFixture({ key: 'a', family: 'brandnew' })]}
        total={1}
        meId={3}
      />,
    );
    await user.click(screen.getByText('More insights (1)'));
    expect(screen.getByRole('region', { name: 'brandnew' })).toBeInTheDocument();
    expect(screen.getByText(/New personal best:/)).toBeInTheDocument();
    expect(screen.queryByText(/Showing/)).toBeNull();
  });

  it('offers "Show all N" when the list is capped and a handler is given', async () => {
    const onShowAll = vi.fn();
    const { user } = renderWithProviders(
      <MoreInsights
        items={[insightFixture({ key: 'a', family: 'streak' })]}
        total={40}
        onShowAll={onShowAll}
      />,
    );
    await user.click(screen.getByText('More insights (40)'));
    await user.click(screen.getByRole('button', { name: 'Show all 40' }));
    expect(onShowAll).toHaveBeenCalledOnce();
    expect(screen.queryByText(/Showing/)).toBeNull();
  });

  it('shows a disabled "Loading…" button while the full list is on its way', async () => {
    const onShowAll = vi.fn();
    const { user } = renderWithProviders(
      <MoreInsights
        items={[insightFixture({ key: 'a', family: 'streak' })]}
        total={40}
        onShowAll={onShowAll}
        loadingAll
      />,
    );
    await user.click(screen.getByText('More insights (40)'));
    expect(screen.getByRole('button', { name: 'Loading…' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Show all 40' })).toBeNull();
  });

  it('has no "Show all" button once everything is listed', async () => {
    const { user } = renderWithProviders(
      <MoreInsights
        items={[insightFixture({ key: 'a', family: 'streak' })]}
        total={1}
        onShowAll={vi.fn()}
      />,
    );
    await user.click(screen.getByText('More insights (1)'));
    expect(screen.queryByRole('button', { name: /Show all/ })).toBeNull();
  });

  it('renders nothing when there is nothing more', () => {
    const { container } = renderWithProviders(<MoreInsights items={[]} total={0} />);
    expect(container).toBeEmptyDOMElement();
  });
});
