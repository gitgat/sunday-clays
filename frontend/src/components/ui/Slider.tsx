import { useId } from 'react';

interface BaseProps {
  label: string;
  min: number;
  max: number;
  step?: number;
  format?: (value: number) => string;
}

export interface SliderProps extends BaseProps {
  value: number;
  onChange: (value: number) => void;
}

export interface RangeSliderProps extends BaseProps {
  value: readonly [number, number];
  onChange: (value: [number, number]) => void;
}

const INPUT = 'h-11 w-full accent-accent';
const plain = (n: number) => String(n);

export function Slider({
  label,
  min,
  max,
  step = 1,
  value,
  onChange,
  format = plain,
}: SliderProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-xs text-text-muted">
        <label htmlFor={id}>{label}</label>
        <output htmlFor={id}>{format(value)}</output>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-valuetext={format(value)}
        onChange={(e) => onChange(Number(e.target.value))}
        className={INPUT}
      />
    </div>
  );
}

/** Two native range inputs; the low thumb never passes the high one. */
export function RangeSlider({
  label,
  min,
  max,
  step = 1,
  value,
  onChange,
  format = plain,
}: RangeSliderProps) {
  const [lo, hi] = value;
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="flex w-full justify-between text-xs text-text-muted">
        <span>{label}</span>
        <span>
          {format(lo)} – {format(hi)}
        </span>
      </legend>
      <input
        type="range"
        aria-label={`${label} minimum`}
        min={min}
        max={max}
        step={step}
        value={lo}
        aria-valuetext={format(lo)}
        onChange={(e) => onChange([Math.min(Number(e.target.value), hi), hi])}
        className={INPUT}
      />
      <input
        type="range"
        aria-label={`${label} maximum`}
        min={min}
        max={max}
        step={step}
        value={hi}
        aria-valuetext={format(hi)}
        onChange={(e) => onChange([lo, Math.max(Number(e.target.value), lo)])}
        className={INPUT}
      />
    </fieldset>
  );
}
