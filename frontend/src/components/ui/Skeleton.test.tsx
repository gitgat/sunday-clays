import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Skeleton } from './Skeleton';

describe('Skeleton', () => {
  it('announces loading with the given label and renders the requested lines', () => {
    const { container } = render(<Skeleton label="Loading chart" lines={5} />);
    expect(screen.getByRole('status', { name: 'Loading chart' })).toHaveAttribute(
      'aria-busy',
      'true',
    );
    expect(container.querySelectorAll('[data-skeleton-line]')).toHaveLength(5);
  });

  it('defaults to three lines labelled Loading', () => {
    const { container } = render(<Skeleton />);
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument();
    expect(container.querySelectorAll('[data-skeleton-line]')).toHaveLength(3);
  });

  it('gives the live region text to announce, not just a name', () => {
    render(<Skeleton label="Loading chart" />);
    expect(screen.getByRole('status')).toHaveTextContent('Loading chart');
  });
});
