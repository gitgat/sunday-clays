import { act, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../../test/render';
import { TOUR_STEPS } from './steps';
import { TourDialog } from './TourDialog';

function box(width: number, height: number): DOMRect {
  return {
    x: 10,
    y: 20,
    top: 20,
    left: 10,
    width,
    height,
    right: 10 + width,
    bottom: 20 + height,
    toJSON: () => ({}),
  };
}

function target(id: string, visible: boolean): HTMLElement {
  const el = document.createElement('div');
  el.dataset.tour = id;
  el.getBoundingClientRect = () => box(visible ? 200 : 0, visible ? 100 : 0);
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.querySelectorAll('[data-tour]').forEach((el) => el.remove());
});

describe('TourDialog', () => {
  it('is a labelled, described modal dialog that starts on step 1 with focus on its title', async () => {
    target('sunday', true);
    renderWithProviders(
      <TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />,
    );
    const dialog = screen.getByRole('dialog', { name: 'The latest Sunday' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAccessibleDescription(TOUR_STEPS[0]?.body ?? '');
    expect(screen.getByText('Step 1 of 5')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Back' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'The latest Sunday' })).toHaveFocus();
  });

  it('walks Next to Done and closes on Done, Skip and Esc', async () => {
    const onClose = vi.fn();
    const { user } = renderWithProviders(
      <TourDialog steps={TOUR_STEPS} preview={false} onClose={onClose} />,
    );
    for (const title of [
      'Which one are you?',
      'Insights and fist bumps',
      'Trophies',
      'Time window',
    ]) {
      await user.click(screen.getByRole('button', { name: 'Next' }));
      expect(screen.getByRole('dialog', { name: title })).toBeInTheDocument();
    }
    await user.click(screen.getByRole('button', { name: 'Back' }));
    expect(screen.getByText('Step 4 of 5')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Done' }));
    await user.click(screen.getByRole('button', { name: 'Skip tour' }));
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it('traps Tab inside the dialog', async () => {
    const { user } = renderWithProviders(
      <TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />,
    );
    await user.click(screen.getByRole('button', { name: 'Next' })); // step 2: Back, Next, Skip
    const skip = screen.getByRole('button', { name: 'Skip tour' });
    skip.focus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Back' })).toHaveFocus();
    await user.tab({ shift: true });
    expect(skip).toHaveFocus();
  });

  it('spotlights the first visible target and scrolls it to the centre', async () => {
    target('sunday', false); // hidden first: skipped
    const shown = target('sunday', true);
    const scroll = vi.spyOn(shown, 'scrollIntoView');
    renderWithProviders(
      <TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />,
    );
    expect(await screen.findByTestId('tour-ring')).toHaveStyle({ width: '208px', height: '108px' });
    expect(scroll).toHaveBeenCalledWith({ block: 'center', behavior: 'smooth' });
  });

  it('centres a step whose target is missing, with no ring', async () => {
    renderWithProviders(
      <TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />,
    );
    await act(async () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve())));
    expect(screen.queryByTestId('tour-ring')).not.toBeInTheDocument();
    expect(screen.getByRole('dialog')).toHaveClass('-translate-x-1/2');
  });

  it('under reduced motion scrolls instantly and has no transition', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) =>
        ({
          matches: query === '(prefers-reduced-motion: reduce)',
          media: query,
          addEventListener: () => undefined,
          removeEventListener: () => undefined,
        }) as unknown as MediaQueryList,
    );
    const shown = target('sunday', true);
    const scroll = vi.spyOn(shown, 'scrollIntoView');
    renderWithProviders(
      <TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />,
    );
    const ring = await screen.findByTestId('tour-ring');
    expect(ring.className).not.toMatch(/transition/);
    expect(scroll).toHaveBeenCalledWith({ block: 'center', behavior: 'auto' });
  });

  it('makes the rest of the page inert while open', () => {
    const outside = document.createElement('div');
    document.body.appendChild(outside);
    const { unmount } = renderWithProviders(
      <TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />,
    );
    expect(outside).toHaveAttribute('inert');
    unmount();
    expect(outside).not.toHaveAttribute('inert');
    outside.remove();
  });

  it('shows the admin preview badge in preview', async () => {
    renderWithProviders(<TourDialog steps={TOUR_STEPS} preview onClose={() => undefined} />, {
      role: 'admin',
    });
    expect(screen.getByText('Admin preview')).toBeInTheDocument();
  });
  it('wraps Tab from the last control to the first', async () => {
    const { user } = renderWithProviders(
      <TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />,
    );
    screen.getByRole('button', { name: 'Next' }).focus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Skip tour' })).toHaveFocus();
  });

  it('keeps the ring on its target when the window resizes', async () => {
    const shown = target('sunday', true);
    renderWithProviders(
      <TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />,
    );
    expect(await screen.findByTestId('tour-ring')).toHaveStyle({ width: '208px' });
    shown.getBoundingClientRect = () => box(300, 100);
    act(() => {
      window.dispatchEvent(new Event('resize'));
    });
    await vi.waitFor(() => expect(screen.getByTestId('tour-ring')).toHaveStyle({ width: '308px' }));
  });
});
