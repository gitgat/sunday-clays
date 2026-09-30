import { useId, type ChangeEvent } from 'react';
import { cx } from './cx';

export interface SelectOption<T extends string> {
  value: T;
  label: string;
}

export interface SelectProps<T extends string> {
  label: string;
  value: T;
  options: readonly SelectOption<T>[];
  onChange: (value: T) => void;
  hideLabel?: boolean;
  className?: string;
}

export function Select<T extends string>({
  label,
  value,
  options,
  onChange,
  hideLabel = false,
  className,
}: SelectProps<T>) {
  const id = useId();
  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const option = options.find((o) => o.value === event.target.value);
    if (option) onChange(option.value);
  };
  return (
    <div className={cx('flex flex-col gap-1', className)}>
      <label htmlFor={id} className={cx('text-xs text-text-muted', hideLabel && 'sr-only')}>
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={handleChange}
        className="min-h-11 rounded-button border border-outline bg-surface px-3 text-sm text-text"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
