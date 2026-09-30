import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../test/render';
import type { Explainer } from '../charts/types';
import { CardHeadingLevel } from './Card';
import { ExplainerPanel, ExplainerToggle, ScopeTag } from './Explainer';

const COPY: Explainer = {
  what: 'How often you shoot each score.',
  read: ['Bars further right are better.', 'Tall and narrow means consistent.'],
  computed: ['Share of your rounds at each score.'],
};

describe('ExplainerPanel', () => {
  it('shows the three labelled parts as plain text lists', () => {
    render(<ExplainerPanel id="p" explainer={COPY} />);
    const panel = screen.getByTestId('explainer-panel');
    expect(panel).toHaveAttribute('id', 'p');
    expect(within(panel).getByRole('heading', { name: 'What this shows' })).toBeVisible();
    expect(within(panel).getByText('How often you shoot each score.')).toBeVisible();
    expect(within(panel).getByRole('heading', { name: 'How to read it' })).toBeVisible();
    expect(within(panel).getAllByRole('listitem')).toHaveLength(3);
    expect(within(panel).getByRole('heading', { name: "How it's worked out" })).toBeVisible();
  });

  it('leaves out "How to read it" when there is nothing to read', () => {
    const { rerender } = render(<ExplainerPanel id="p" explainer={{ ...COPY, read: [] }} />);
    expect(screen.queryByRole('heading', { name: 'How to read it' })).toBeNull();
    rerender(<ExplainerPanel id="p" explainer={{ what: 'x', computed: ['y'] }} />);
    expect(screen.queryByRole('heading', { name: 'How to read it' })).toBeNull();
  });

  it('nests its headings under the card heading level', () => {
    render(
      <CardHeadingLevel value={3}>
        <ExplainerPanel id="p" explainer={COPY} />
      </CardHeadingLevel>,
    );
    expect(screen.getByRole('heading', { name: 'What this shows' }).tagName).toBe('H4');
  });
});

describe('ExplainerToggle', () => {
  it('is a 44 px button naming the panel it controls', async () => {
    const user = userEvent.setup();
    const seen: boolean[] = [];
    render(
      <ExplainerToggle
        label="About this chart"
        panelId="panel-1"
        open={false}
        onToggle={() => seen.push(true)}
      />,
    );
    const button = screen.getByRole('button', { name: 'About this chart' });
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(button).toHaveAttribute('aria-controls', 'panel-1');
    expect(button.className).toContain('min-h-11');
    await user.click(button);
    expect(seen).toEqual([true]);
  });

  it('can be a compact question mark with the same accessible name', () => {
    render(<ExplainerToggle label="About Rounds" panelId="p" open compact onToggle={() => {}} />);
    const button = screen.getByRole('button', { name: 'About Rounds' });
    expect(button).toHaveTextContent('?');
    expect(button).toHaveAttribute('aria-expanded', 'true');
    expect(button.className).toContain('min-w-11');
  });
});

describe('ScopeTag', () => {
  it('names the active window for a windowed chart', () => {
    renderWithProviders(<ScopeTag scope="windowed" />, { route: '/?w=6m' });
    expect(screen.getByText('Last 6 months')).toBeVisible();
  });

  it('names the window with the dates it covers, once the latest Sunday is known', async () => {
    renderWithProviders(<ScopeTag scope="windowed" />, { route: '/?w=6m' });
    expect(await screen.findByText('Last 6 months · Mar 28 – Sep 27')).toBeVisible();
  });

  it('says Lifetime for career totals and One year at a time for a calendar', () => {
    const { unmount } = renderWithProviders(<ScopeTag scope="lifetime" />, { route: '/?w=6m' });
    expect(screen.getByText('Lifetime')).toBeVisible();
    unmount();
    renderWithProviders(<ScopeTag scope="year" />, { route: '/?w=6m' });
    expect(screen.getByText('One year at a time')).toBeVisible();
  });

  it('names a custom window by its dates', () => {
    renderWithProviders(<ScopeTag scope="windowed" />, { route: '/?w=2025-03-01..2025-09-28' });
    expect(screen.getByText('Mar 1, 2025 – Sep 28, 2025')).toBeVisible();
  });

  it('says the default window when the URL has none', () => {
    renderWithProviders(<ScopeTag scope="windowed" />);
    expect(screen.getByText('Last 8 weeks')).toBeVisible();
  });

  it('says All time for an all-time chart, whatever the window', () => {
    renderWithProviders(<ScopeTag scope="all-time" />, { route: '/?w=6m' });
    expect(screen.getByText('All time')).toBeVisible();
  });

  it('renders nothing without a scope', () => {
    const { container } = renderWithProviders(<ScopeTag scope={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
