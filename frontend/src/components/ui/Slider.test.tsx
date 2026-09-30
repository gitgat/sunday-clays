import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RangeSlider, Slider } from './Slider';

describe('Slider', () => {
  it('reports numeric values and shows the formatted value', () => {
    const onChange = vi.fn();
    render(
      <Slider
        label="Min rounds"
        min={0}
        max={50}
        value={5}
        onChange={onChange}
        format={(n) => `${n} rounds`}
      />,
    );
    expect(screen.getByText('5 rounds')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Min rounds'), { target: { value: '12' } });
    expect(onChange).toHaveBeenCalledWith(12);
  });

  it('shows the raw number without a formatter', () => {
    render(<Slider label="Top" min={1} max={20} value={10} onChange={() => undefined} />);
    expect(screen.getByText('10')).toBeInTheDocument();
  });
});

describe('RangeSlider', () => {
  it('moves each thumb and never lets the low thumb pass the high one', () => {
    const onChange = vi.fn();
    render(
      <RangeSlider
        label="Temperature"
        min={0}
        max={100}
        value={[40, 70]}
        onChange={onChange}
        format={(n) => `${n}°F`}
      />,
    );
    expect(screen.getByText('40°F – 70°F')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Temperature minimum'), { target: { value: '50' } });
    expect(onChange).toHaveBeenLastCalledWith([50, 70]);
    fireEvent.change(screen.getByLabelText('Temperature minimum'), { target: { value: '90' } });
    expect(onChange).toHaveBeenLastCalledWith([70, 70]);
    fireEvent.change(screen.getByLabelText('Temperature maximum'), { target: { value: '20' } });
    expect(onChange).toHaveBeenLastCalledWith([40, 40]);
    fireEvent.change(screen.getByLabelText('Temperature maximum'), { target: { value: '80' } });
    expect(onChange).toHaveBeenLastCalledWith([40, 80]);
  });

  it('shows raw numbers without a formatter', () => {
    render(
      <RangeSlider label="Gust" min={0} max={40} value={[0, 40]} onChange={() => undefined} />,
    );
    expect(screen.getByText('0 – 40')).toBeInTheDocument();
  });
});

describe('slider value text', () => {
  it('announces the formatted value, not the raw number', () => {
    render(
      <>
        <Slider
          label="Min rounds"
          min={0}
          max={50}
          value={5}
          onChange={() => undefined}
          format={(n) => `${n} rounds`}
        />
        <RangeSlider
          label="Temperature"
          min={0}
          max={100}
          value={[40, 70]}
          onChange={() => undefined}
          format={(n) => `${n}°F`}
        />
      </>,
    );
    expect(screen.getByLabelText('Min rounds')).toHaveAttribute('aria-valuetext', '5 rounds');
    expect(screen.getByLabelText('Temperature minimum')).toHaveAttribute('aria-valuetext', '40°F');
    expect(screen.getByLabelText('Temperature maximum')).toHaveAttribute('aria-valuetext', '70°F');
  });
});
