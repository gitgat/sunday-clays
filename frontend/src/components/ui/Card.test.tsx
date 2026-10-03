import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Card, CardHeadingLevel } from './Card';

describe('Card', () => {
  it('titles with an h2 by default and an h3 inside CardHeadingLevel 3', () => {
    render(
      <>
        <Card title="Outer">a</Card>
        <CardHeadingLevel value={3}>
          <Card title="Inner">b</Card>
        </CardHeadingLevel>
      </>,
    );
    expect(screen.getByRole('heading', { level: 2, name: 'Outer' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: 'Inner' })).toBeInTheDocument();
  });

  it('is a region named by its title, with subtitle and actions', () => {
    render(
      <Card title="Attendance" subtitle="Since 2018" actions={<button type="button">CSV</button>}>
        body
      </Card>,
    );
    const region = screen.getByRole('region', { name: 'Attendance' });
    expect(region).toHaveTextContent('Since 2018');
    expect(region).toHaveTextContent('body');
    expect(screen.getByRole('button', { name: 'CSV' })).toBeInTheDocument();
  });

  it('wraps a long title instead of truncating it', () => {
    render(<Card title="Score distribution vs club">x</Card>);
    const heading = screen.getByRole('heading', { name: 'Score distribution vs club' });
    expect(heading).toHaveClass('break-words');
    expect(heading).not.toHaveClass('truncate');
  });

  it('renders no header and no accessible name without a title', () => {
    const { container } = render(<Card>plain</Card>);
    expect(container.querySelector('header')).toBeNull();
    expect(container.querySelector('section')).not.toHaveAttribute('aria-labelledby');
  });

  it('takes an id as a focusable link anchor', () => {
    render(
      <Card id="chart-trend" title="Scores">
        x
      </Card>,
    );
    const region = screen.getByRole('region', { name: 'Scores' });
    expect(region).toHaveAttribute('id', 'chart-trend');
    expect(region).toHaveAttribute('tabindex', '-1');
    expect(region).toHaveClass('scroll-mt-28', 'focus:outline-none');
    render(<Card title="Plain">y</Card>);
    expect(screen.getByRole('region', { name: 'Plain' })).not.toHaveAttribute('tabindex');
    expect(screen.getByRole('region', { name: 'Plain' })).not.toHaveClass('scroll-mt-28');
  });
});

describe('Card tour target', () => {
  it('renders data-tour only when given', () => {
    const { container, rerender } = render(<Card title="x" tour="sunday" />);
    expect(container.querySelector('section')).toHaveAttribute('data-tour', 'sunday');
    rerender(<Card title="x" />);
    expect(container.querySelector('section')).not.toHaveAttribute('data-tour');
  });
});
