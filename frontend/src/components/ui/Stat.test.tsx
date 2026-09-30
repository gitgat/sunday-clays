import { render, screen } from '@testing-library/react';
import { expectExplainer } from '../../test/charts';
import { renderWithProviders } from '../../test/render';
import { describe, expect, it } from 'vitest';
import { Stat } from './Stat';

describe('Stat', () => {
  it.each([
    [2, 'up', '+2.0'],
    [-1.54, 'down', '−1.5'],
    [0, 'flat', '0.0'],
  ])('renders delta %s as trend %s with its sign', (delta, trend, visible) => {
    const { container } = render(<Stat label="Avg" value="35.2" delta={delta} />);
    const el = container.querySelector('[data-trend]');
    expect(el).toHaveAttribute('data-trend', trend);
    expect(el).toHaveTextContent(visible);
  });

  it('tells screen readers the direction in words', () => {
    render(<Stat label="Avg" value="35.2" delta={-3} />);
    expect(screen.getByText('down', { exact: false })).toHaveClass('sr-only');
  });

  it('omits the delta when null and shows the hint', () => {
    const { container } = render(
      <Stat label="Rounds" value={120} delta={null} hint="since 2020" />,
    );
    expect(container.querySelector('[data-trend]')).toBeNull();
    expect(screen.getByText('since 2020')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();
  });

  it('uses a custom delta formatter', () => {
    render(<Stat label="Rank" value={3} delta={2} formatDelta={(n) => `${n} places`} />);
    expect(screen.getByText('+2 places')).toBeInTheDocument();
  });

  it('colors only the hidden arrow by trend and keeps the number in the text color', () => {
    const { container } = render(<Stat label="Avg" value="35.2" delta={2} />);
    const trend = container.querySelector('[data-trend]');
    const arrow = trend?.querySelector('svg');
    expect(arrow).toHaveAttribute('aria-hidden', 'true');
    expect(arrow).toHaveClass('stroke-accent');
    expect(screen.getByText('+2.0')).toHaveClass('text-text');
    expect(trend?.className).not.toMatch(/text-accent/);
  });

  it.each([NaN, Infinity, -Infinity])('renders no delta for a non-finite change (%s)', (delta) => {
    const { container } = render(<Stat label="Avg" value="35.2" delta={delta} />);
    expect(container.querySelector('[data-trend]')).toBeNull();
    expect(container).not.toHaveTextContent('NaN');
  });

  it('shows a compact ? disclosure with the same three-part panel when it has an explainer', async () => {
    const { container } = render(
      <Stat
        label="Rating"
        value="34.5"
        explainer={{
          what: 'Our estimate of your current skill, in targets.',
          computed: ['Recent rounds count more than old ones.'],
        }}
      />,
    );
    const button = screen.getByRole('button', { name: 'About Rating' });
    expect(button).toHaveTextContent('?');
    await expectExplainer(container, 'About Rating', { read: false });
  });

  it('puts the ? in the label row with normal flow, so nothing is offset or clipped', async () => {
    const { container, user } = renderWithProviders(
      <Stat label="Rating" value="34.5" explainer={{ what: 'x', computed: ['y'] }} />,
    );
    const button = screen.getByRole('button', { name: 'About Rating' });
    const row = screen.getByText('Rating').parentElement as HTMLElement;
    expect(row).toContainElement(button);
    expect(row).toHaveClass('flex', 'items-center', 'justify-between');
    expect(container.innerHTML).not.toMatch(/absolute|-top-|-mr-|pr-11/);
    await user.click(button);
    expect(screen.getByTestId('explainer-panel')).toBeVisible();
  });

  it('has no disclosure without an explainer', () => {
    render(<Stat label="Rating" value="34.5" />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('tags a windowed stat with the active window', () => {
    renderWithProviders(
      <Stat
        label="Rounds"
        value={12}
        explainer={{ what: 'x', computed: ['y'], scope: 'windowed' }}
      />,
      { route: '/?w=6m' },
    );
    expect(screen.getByText('Last 6 months')).toBeVisible();
  });
});
