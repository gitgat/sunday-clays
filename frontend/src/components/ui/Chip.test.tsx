import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Chip } from './Chip';

describe('Chip', () => {
  it('is a toggle button exposing its pressed state', async () => {
    const onClick = vi.fn();
    render(
      <Chip selected onClick={onClick}>
        Sporting
      </Chip>,
    );
    const chip = screen.getByRole('button', { name: 'Sporting' });
    expect(chip).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(chip);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('is static text without onClick, and offers a labelled remove button', async () => {
    const onRemove = vi.fn();
    render(
      <Chip onRemove={onRemove} removeLabel="Clear round type filter">
        Filtered: Sporting
      </Chip>,
    );
    expect(screen.queryByRole('button', { name: 'Filtered: Sporting' })).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Clear round type filter' }));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it('falls back to a generic remove label', () => {
    render(<Chip onRemove={() => undefined}>x</Chip>);
    expect(screen.getByRole('button', { name: 'Remove' })).toBeInTheDocument();
  });
});
