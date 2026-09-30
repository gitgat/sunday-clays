import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { classColor, contrast } from '../../test/contrast';
import { colors } from '../../theme/tokens';
import { Toggle } from './Toggle';

describe('Toggle', () => {
  it('is a switch that reports the flipped state', async () => {
    const onChange = vi.fn();
    render(<Toggle label="Best round only" checked={false} onChange={onChange} />);
    const toggle = screen.getByRole('switch', { name: 'Best round only' });
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    await userEvent.click(toggle);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('reports false when turning off, and ignores clicks while disabled', async () => {
    const onChange = vi.fn();
    const { rerender } = render(<Toggle label="Recalibrate" checked onChange={onChange} />);
    await userEvent.click(screen.getByRole('switch', { name: 'Recalibrate' }));
    expect(onChange).toHaveBeenCalledWith(false);
    rerender(<Toggle label="Recalibrate" checked disabled onChange={onChange} />);
    await userEvent.click(screen.getByRole('switch', { name: 'Recalibrate' }));
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it('keeps the on track 3:1 from the off track and both backgrounds, and the knob 3:1 from its track', () => {
    const view = (checked: boolean) => (
      <Toggle label="Best round only" checked={checked} onChange={() => undefined} />
    );
    const parts = () => {
      const track = screen.getByRole('switch').querySelector('[aria-hidden="true"]');
      const knob = track?.firstElementChild;
      return {
        track: classColor(track?.getAttribute('class') ?? '', 'bg'),
        edge: classColor(track?.getAttribute('class') ?? '', 'border'),
        knob: classColor(knob?.getAttribute('class') ?? '', 'bg'),
      };
    };
    const { rerender } = render(view(false));
    const off = parts();
    rerender(view(true));
    const on = parts();
    expect(contrast(on.track, off.track)).toBeGreaterThanOrEqual(3);
    for (const page of [colors.elevated, colors.surface]) {
      expect(contrast(on.edge, page)).toBeGreaterThanOrEqual(3);
      expect(contrast(off.edge, page)).toBeGreaterThanOrEqual(3);
    }
    expect(contrast(on.knob, on.track)).toBeGreaterThanOrEqual(3);
    expect(contrast(off.knob, off.track)).toBeGreaterThanOrEqual(3);
  });
});
