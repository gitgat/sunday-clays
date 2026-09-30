import { useId } from 'react';

export function TextField({
  label,
  value,
  onChange,
  type = 'text',
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: 'text' | 'number' | 'date';
}) {
  const id = useId();
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <label htmlFor={id} className="text-sm">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-11 w-full min-w-0 rounded-button border border-outline-variant bg-elevated px-3"
      />
    </div>
  );
}

export function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  const id = useId();
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <label htmlFor={id} className="text-sm">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-11 w-full min-w-0 rounded-button border border-outline-variant bg-elevated px-3"
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

export const STATUS_OPTIONS = [
  { value: '', label: 'Choose…' },
  { value: 'member', label: 'Member' },
  { value: 'guest', label: 'Guest' },
  { value: 'deceased', label: 'Deceased (memorial)' },
];

export const ROUND_TYPE_OPTIONS = [
  { value: '', label: 'Choose…' },
  { value: 'sporting', label: 'Sporting' },
  { value: 'super_sporting', label: 'Super Sporting' },
];
