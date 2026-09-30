import { LoaderCircle } from 'lucide-react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cx } from './cx';

export type ButtonVariant = 'primary' | 'tonal' | 'ghost' | 'danger';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  icon?: ReactNode;
}

/** Hover darkens the background only (never the text), so text contrast only rises. */
const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-text hover:bg-[color-mix(in_srgb,var(--color-primary)_85%,black)]',
  tonal: 'bg-elevated text-text border border-outline-variant hover:border-outline',
  ghost: 'bg-transparent text-text-muted hover:bg-elevated hover:text-text',
  danger:
    'bg-error-container text-text hover:bg-[color-mix(in_srgb,var(--color-error-container)_85%,black)]',
};

export function Button({
  variant = 'primary',
  loading = false,
  icon,
  className,
  children,
  disabled,
  type = 'button',
  onClick,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      // Loading keeps the button focusable (native `disabled` would drop focus): announce it
      // as disabled and swallow clicks, which also blocks a submit button's form submission.
      aria-disabled={loading || undefined}
      aria-busy={loading || undefined}
      onClick={(event) => {
        if (loading) {
          event.preventDefault();
          return;
        }
        onClick?.(event);
      }}
      className={cx(
        'inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-button px-4 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 aria-disabled:cursor-not-allowed aria-disabled:opacity-50',
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {loading ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}
