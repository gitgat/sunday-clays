import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../test/render';
import { THIN_WINDOW_SUNDAYS, ThinWindowNudge, isThinWindow } from './ThinWindowNudge';

describe('isThinWindow', () => {
  it('is thin below 12 Sundays', () => {
    expect(THIN_WINDOW_SUNDAYS).toBe(12);
    expect(isThinWindow(0)).toBe(true);
    expect(isThinWindow(11)).toBe(true);
    expect(isThinWindow(12)).toBe(false);
  });
});

describe('ThinWindowNudge', () => {
  it('names the count and the period, and offers 12M and All', async () => {
    const { user, router } = renderWithProviders(<ThinWindowNudge sundays={7} />);
    expect(screen.getByRole('note')).toHaveTextContent(
      'Only 7 Sundays in the last 8 weeks. Weather patterns need more.',
    );
    await user.click(screen.getByRole('button', { name: 'Show the last 12 months' }));
    expect(router.state.location.search).toBe('?w=12m');
  });

  it('switches to all time in one tap', async () => {
    const { user, router } = renderWithProviders(<ThinWindowNudge sundays={3} />);
    await user.click(screen.getByRole('button', { name: 'Show all time' }));
    expect(router.state.location.search).toBe('?w=all');
  });

  it("says one Sunday and none in plain words, with the caller's own follow-up", () => {
    const { unmount } = renderWithProviders(
      <ThinWindowNudge sundays={1} need="Charts need more." />,
    );
    expect(screen.getByRole('note')).toHaveTextContent(
      'Only 1 Sunday in the last 8 weeks. Charts need more.',
    );
    unmount();
    renderWithProviders(<ThinWindowNudge sundays={0} />);
    expect(screen.getByRole('note')).toHaveTextContent('No Sundays in the last 8 weeks.');
  });

  it('draws nothing once the window has enough Sundays', () => {
    renderWithProviders(<ThinWindowNudge sundays={12} />);
    expect(screen.queryByRole('note')).toBeNull();
  });

  it('offers only All when 12M is already chosen, and nothing wider on All', () => {
    const { unmount } = renderWithProviders(<ThinWindowNudge sundays={9} />, {
      route: '/?w=12m',
    });
    expect(screen.getByRole('note')).toHaveTextContent('in the last 12 months');
    expect(screen.queryByRole('button', { name: 'Show the last 12 months' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Show all time' })).toBeVisible();
    unmount();
    renderWithProviders(<ThinWindowNudge sundays={9} />, { route: '/?w=all' });
    expect(screen.getByRole('note')).toHaveTextContent('Only 9 Sundays on record.');
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('names a custom window by its dates and a year to date in words', () => {
    const { unmount } = renderWithProviders(<ThinWindowNudge sundays={4} />, {
      route: '/?w=2026-03-01..2026-04-05',
    });
    expect(screen.getByRole('note')).toHaveTextContent('in Mar 1, 2026 – Apr 5, 2026.');
    unmount();
    renderWithProviders(<ThinWindowNudge sundays={4} />, { route: '/?w=ytd' });
    expect(screen.getByRole('note')).toHaveTextContent('in this year to date.');
  });

  it('says a page-specific message in place of the Sunday count, still with 12M and All', async () => {
    const { user, router } = renderWithProviders(
      <ThinWindowNudge sundays={0} message="No station sheets in the last 8 weeks." />,
    );
    expect(screen.getByRole('note')).toHaveTextContent('No station sheets in the last 8 weeks.');
    expect(screen.getByRole('note')).not.toHaveTextContent('No Sundays');
    await user.click(screen.getByRole('button', { name: 'Show the last 12 months' }));
    expect(router.state.location.search).toBe('?w=12m');
  });

  it('shows the caller\u2019s own action instead of the widening buttons', () => {
    renderWithProviders(
      <ThinWindowNudge
        sundays={0}
        message="Nothing since the reset."
        action={<button>Mine</button>}
      />,
    );
    expect(screen.getByRole('button', { name: 'Mine' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Show all time' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Show the last 12 months' })).toBeNull();
  });

  it('can name itself for screen readers', () => {
    renderWithProviders(
      <ThinWindowNudge sundays={0} message="Nothing here." label="Widen the time window" />,
    );
    expect(screen.getByRole('note', { name: 'Widen the time window' })).toHaveTextContent(
      'Nothing here.',
    );
  });

  it('keeps 44 px tap targets', () => {
    renderWithProviders(<ThinWindowNudge sundays={4} />);
    for (const button of screen.getAllByRole('button')) expect(button).toHaveClass('min-h-11');
  });
});
