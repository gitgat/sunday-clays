import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { EmptyState } from './EmptyState';

describe('EmptyState', () => {
  it('shows title, description, icon and action', () => {
    render(
      <EmptyState
        title="No weather yet"
        description="Weather sync is off."
        icon={<svg data-testid="icon" />}
        action={<button type="button">Retry</button>}
      />,
    );
    expect(screen.getByRole('heading', { name: 'No weather yet' })).toBeInTheDocument();
    expect(screen.getByText('Weather sync is off.')).toBeInTheDocument();
    expect(screen.getByTestId('icon')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });

  it('renders only the title when nothing else is given', () => {
    const { container } = render(<EmptyState title="Nothing here" />);
    expect(container.querySelectorAll('p')).toHaveLength(0);
    expect(screen.queryByRole('button')).toBeNull();
  });
});
