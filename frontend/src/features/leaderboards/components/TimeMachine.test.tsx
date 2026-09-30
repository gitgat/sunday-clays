import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { TimeMachine } from './TimeMachine';

const DATES = ['2026-09-06', '2026-09-13', '2026-09-27'];

describe('TimeMachine ("Board as of")', () => {
  it('sits on the latest event when no as_of is chosen', () => {
    render(<TimeMachine dates={DATES} asOf={null} onChange={vi.fn()} />);
    expect(screen.getByLabelText('Board as of')).toHaveValue('2');
    expect(screen.getByText('Latest', { selector: 'output' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Latest' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next Sunday' })).toBeDisabled();
  });

  it('parks the thumb on the previous event but labels the date actually queried', () => {
    render(<TimeMachine dates={DATES} asOf="2026-09-20" onChange={vi.fn()} />);
    expect(screen.getByLabelText('Board as of')).toHaveValue('1');
    expect(screen.getByText('Sep 20, 2026', { selector: 'output' })).toBeInTheDocument();
  });

  it('labels an as_of before the first event with that date, and cannot step earlier', () => {
    render(<TimeMachine dates={DATES} asOf="2019-01-01" onChange={vi.fn()} />);
    expect(screen.getByLabelText('Board as of')).toHaveValue('0');
    expect(screen.getByText('Jan 1, 2019', { selector: 'output' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous Sunday' })).toBeDisabled();
  });

  it('reports the event date under the slider', () => {
    const onChange = vi.fn();
    render(<TimeMachine dates={DATES} asOf={null} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Board as of'), { target: { value: '0' } });
    expect(onChange).toHaveBeenLastCalledWith('2026-09-06');
  });

  it('clears the date when the slider reaches the newest Sunday, and from Latest', () => {
    const onChange = vi.fn();
    render(<TimeMachine dates={DATES} asOf="2026-09-06" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Board as of'), { target: { value: '2' } });
    expect(onChange).toHaveBeenLastCalledWith(null);
    onChange.mockClear();
    fireEvent.click(screen.getByRole('button', { name: 'Latest' }));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('steps one Sunday back and forward, and forward from the second-to-last is the latest board', () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <TimeMachine dates={DATES} asOf="2026-09-13" onChange={onChange} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Previous Sunday' }));
    expect(onChange).toHaveBeenLastCalledWith('2026-09-06');
    fireEvent.click(screen.getByRole('button', { name: 'Next Sunday' }));
    expect(onChange).toHaveBeenLastCalledWith(null);
    rerender(<TimeMachine dates={DATES} asOf="2026-09-06" onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Next Sunday' }));
    expect(onChange).toHaveBeenLastCalledWith('2026-09-13');
    fireEvent.click(screen.getByRole('button', { name: 'Previous Sunday' }));
    expect(onChange).toHaveBeenCalledTimes(3);
  });

  it('renders nothing without event dates', () => {
    const { container } = render(<TimeMachine dates={[]} asOf={null} onChange={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });
});
