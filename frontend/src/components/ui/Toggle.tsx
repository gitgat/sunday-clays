import { cx } from './cx';

export interface ToggleProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}

export function Toggle({ label, checked, onChange, disabled = false }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="inline-flex min-h-11 items-center gap-3 text-sm text-text disabled:opacity-50"
    >
      <span
        aria-hidden="true"
        className={cx(
          'relative inline-flex h-6 w-11 shrink-0 rounded-full border-2 transition-colors',
          checked ? 'border-accent bg-accent' : 'border-outline bg-surface',
        )}
      >
        <span
          className={cx(
            'absolute top-0.5 size-4 rounded-full transition-transform',
            checked ? 'translate-x-5.5 bg-surface' : 'translate-x-0.5 bg-outline',
          )}
        />
      </span>
      {label}
    </button>
  );
}
