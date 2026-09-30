import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { classColor, contrast, scale } from '../../test/contrast';
import { colors } from '../../theme/tokens';
import { Button } from './Button';

/** Resolved text/background colors at rest and on hover; a transparent button sits on a card. */
function restAndHover(className: string) {
  const bg = className.includes('bg-transparent') ? colors.elevated : classColor(className, 'bg');
  const rest = { fg: classColor(className, 'text'), bg };
  const hover = { ...rest };
  if (/(^|\s)hover:text-/.test(className)) hover.fg = classColor(className, 'hover:text');
  const mix = /hover:bg-\[color-mix\(in_srgb,var\(--color-([a-z-]+)\)_(\d+)%,black\)\]/.exec(
    className,
  );
  if (mix) hover.bg = scale(classColor(`bg-${mix[1] ?? ''}`, 'bg'), Number(mix[2]) / 100);
  else if (/(^|\s)hover:bg-/.test(className)) hover.bg = classColor(className, 'hover:bg');
  const dim = /hover:brightness-(\d+)/.exec(className);
  if (dim) {
    hover.fg = scale(hover.fg, Number(dim[1]) / 100);
    hover.bg = scale(hover.bg, Number(dim[1]) / 100);
  }
  return { rest, hover };
}

describe('Button', () => {
  it('calls onClick and defaults to type=button so it never submits a form by accident', async () => {
    const onClick = vi.fn();
    const onSubmit = vi.fn((e: SubmitEvent) => e.preventDefault());
    render(
      <form onSubmit={(e) => onSubmit(e.nativeEvent as SubmitEvent)}>
        <Button onClick={onClick}>Save</Button>
      </form>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('stays focusable while loading (aria-disabled, busy) but ignores clicks and never submits', async () => {
    const onClick = vi.fn();
    const onSubmit = vi.fn((e: SubmitEvent) => e.preventDefault());
    render(
      <form onSubmit={(e) => onSubmit(e.nativeEvent as SubmitEvent)}>
        <Button type="submit" loading onClick={onClick}>
          Upload
        </Button>
      </form>,
    );
    const button = screen.getByRole('button', { name: 'Upload' });
    expect(button).toHaveAttribute('aria-disabled', 'true');
    expect(button).toHaveAttribute('aria-busy', 'true');
    expect(button).toBeEnabled();
    button.focus();
    expect(button).toHaveFocus();
    await userEvent.click(button);
    await userEvent.keyboard('{Enter}');
    expect(onClick).not.toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('renders the icon when not loading and honours disabled', () => {
    render(
      <Button disabled variant="danger" icon={<svg data-testid="icon" />}>
        Delete
      </Button>,
    );
    expect(screen.getByTestId('icon')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Delete' })).not.toHaveAttribute('aria-busy');
  });

  it.each(['primary', 'tonal', 'ghost', 'danger'] as const)(
    'keeps 4.5:1 text contrast at rest and on hover (%s, on a card)',
    (variant) => {
      render(<Button variant={variant}>Go</Button>);
      const { rest, hover } = restAndHover(screen.getByRole('button', { name: 'Go' }).className);
      expect(contrast(rest.fg, rest.bg), 'rest').toBeGreaterThanOrEqual(4.5);
      expect(contrast(hover.fg, hover.bg), 'hover').toBeGreaterThanOrEqual(4.5);
    },
  );
});
