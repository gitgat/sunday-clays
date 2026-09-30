import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { cx } from './cx';

export interface ChipProps {
  children: ReactNode;
  selected?: boolean;
  onClick?: () => void;
  /** When set, renders a remove button labelled `removeLabel`. */
  onRemove?: () => void;
  removeLabel?: string;
  icon?: ReactNode;
}

const BASE = 'inline-flex min-h-11 items-center gap-1.5 rounded-button border px-3 text-sm';

export function Chip({
  children,
  selected = false,
  onClick,
  onRemove,
  removeLabel,
  icon,
}: ChipProps) {
  const tone = selected
    ? 'border-accent bg-accent/15 text-text'
    : 'border-outline-variant bg-transparent text-text-muted';
  const content = (
    <>
      {icon}
      {children}
    </>
  );
  return (
    <span className="inline-flex items-center">
      {onClick === undefined ? (
        <span className={cx(BASE, tone)}>{content}</span>
      ) : (
        <button type="button" aria-pressed={selected} onClick={onClick} className={cx(BASE, tone)}>
          {content}
        </button>
      )}
      {onRemove !== undefined && (
        <button
          type="button"
          aria-label={removeLabel ?? 'Remove'}
          onClick={onRemove}
          className="-ml-1 inline-flex size-11 items-center justify-center rounded-full text-text-muted hover:text-text"
        >
          <X aria-hidden="true" className="size-4" />
        </button>
      )}
    </span>
  );
}
