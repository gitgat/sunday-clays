import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { classColor, contrast } from '../../test/contrast';
import { colors } from '../../theme/tokens';
import { Select } from './Select';

const OPTIONS = [
  { value: 'avg', label: 'Average' },
  { value: 'max', label: 'Best' },
] as const;

describe('Select', () => {
  it('is labelled and reports the typed value of the chosen option', async () => {
    const onChange = vi.fn();
    render(<Select label="Aggregate" value="avg" options={OPTIONS} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByLabelText('Aggregate'), 'Best');
    expect(onChange).toHaveBeenCalledWith('max');
  });

  it('can hide its label visually while keeping it accessible', () => {
    render(
      <Select
        label="Aggregate"
        hideLabel
        value="avg"
        options={OPTIONS}
        onChange={() => undefined}
      />,
    );
    expect(screen.getByText('Aggregate')).toHaveClass('sr-only');
    expect(screen.getByLabelText('Aggregate')).toHaveValue('avg');
  });

  it('draws its border at 3:1 against cards and the page', () => {
    render(<Select label="Aggregate" value="avg" options={OPTIONS} onChange={() => undefined} />);
    const border = classColor(screen.getByLabelText('Aggregate').className, 'border');
    expect(contrast(border, colors.elevated)).toBeGreaterThanOrEqual(3);
    expect(contrast(border, colors.surface)).toBeGreaterThanOrEqual(3);
  });

  it('ignores a value that is not one of its options', () => {
    const onChange = vi.fn();
    render(<Select label="Aggregate" value="avg" options={OPTIONS} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Aggregate'), { target: { value: 'bogus' } });
    expect(onChange).not.toHaveBeenCalled();
  });
});
