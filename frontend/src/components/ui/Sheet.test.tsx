import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { Sheet } from './Sheet';

function Harness({ onClose = vi.fn() }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        More
      </button>
      <Sheet
        open={open}
        title="More"
        placement="center"
        size="full"
        onClose={() => {
          onClose();
          setOpen(false);
        }}
      >
        <a href="/club">Club</a>
        <button type="button">Log out</button>
      </Sheet>
    </>
  );
}

describe('Sheet', () => {
  it('renders nothing while closed', () => {
    render(
      <Sheet open={false} title="x" onClose={() => undefined}>
        body
      </Sheet>,
    );
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('opens as a labelled modal dialog, focuses it and locks body scroll', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    const dialog = screen.getByRole('dialog', { name: 'More' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveFocus();
    expect(document.body.style.overflow).toBe('hidden');
  });

  it('closes on Escape and restores focus and scroll', async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const opener = screen.getByRole('button', { name: 'More' });
    await userEvent.click(opener);
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(opener).toHaveFocus();
    expect(document.body.style.overflow).toBe('');
  });

  it('closes from the close button and from the backdrop', async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    await userEvent.click(screen.getByTestId('sheet-backdrop'));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('keeps Tab focus inside the dialog in both directions', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    const close = screen.getByRole('button', { name: 'Close' });
    const last = screen.getByRole('button', { name: 'Log out' });
    last.focus();
    await userEvent.tab();
    expect(close).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(last).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(screen.getByRole('link', { name: 'Club' })).toHaveFocus();
  });

  it('wraps Tab back to Close when Close is the only control', async () => {
    render(
      <Sheet open title="Empty" onClose={() => undefined}>
        text only
      </Sheet>,
    );
    const close = screen.getByRole('button', { name: 'Close' });
    close.focus();
    await userEvent.tab();
    expect(close).toHaveFocus();
  });

  it('Shift+Tab right after opening wraps to the last control', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    expect(screen.getByRole('dialog', { name: 'More' })).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(screen.getByRole('button', { name: 'Log out' })).toHaveFocus();
  });

  it('makes the rest of the page inert while open, then un-inerts it before restoring focus', async () => {
    const { container } = render(<Harness />);
    const opener = screen.getByRole('button', { name: 'More' });
    await userEvent.click(opener);
    expect(container).toHaveAttribute('inert');
    expect(screen.getByRole('dialog', { name: 'More' }).closest('[inert]')).toBeNull();
    await userEvent.keyboard('{Escape}');
    expect(container).not.toHaveAttribute('inert');
    expect(opener).toHaveFocus();
  });

  it('leaves elements that were already inert alone', async () => {
    const outside = document.createElement('div');
    outside.setAttribute('inert', '');
    document.body.append(outside);
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    await userEvent.keyboard('{Escape}');
    expect(outside).toHaveAttribute('inert');
    outside.remove();
  });

  it('is a full-height sheet with rounded top corners at the bottom edge', () => {
    render(
      <Sheet open title="Chart" size="full" onClose={() => undefined}>
        chart
      </Sheet>,
    );
    const dialog = screen.getByRole('dialog', { name: 'Chart' });
    expect(dialog).toHaveClass('rounded-t-sheet', 'h-[95dvh]');
    expect(dialog).not.toHaveClass('h-[90dvh]');
  });

  it('opens and closes cleanly when focus was on a non-HTML element', () => {
    const view = (open: boolean) => (
      <>
        <svg tabIndex={0} data-testid="chart" />
        <Sheet open={open} title="Details" onClose={() => undefined}>
          body
        </Sheet>
      </>
    );
    const { rerender } = render(view(false));
    const svg = screen.getByTestId('chart');
    svg.focus();
    expect(svg).toHaveFocus();
    rerender(view(true));
    expect(screen.getByRole('dialog', { name: 'Details' })).toHaveFocus();
    expect(document.body.style.overflow).toBe('hidden');
    rerender(view(false));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.body.style.overflow).toBe('');
  });
});
