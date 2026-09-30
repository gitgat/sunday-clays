import { createContext, useContext, useId, type ReactNode } from 'react';
import { cx } from './cx';

export interface CardProps {
  /** Anchor for links (Plan 12 chart targets: `chart-{urlKey}`); the card is then focusable. */
  id?: string;
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
}

/**
 * The heading level of a Card's title. Cards are h2 by default; a page that puts its own h2 sections
 * around a group of cards wraps them in `<CardHeadingLevel value={3}>` so the outline nests.
 */
export const CardHeadingLevel = createContext<2 | 3>(2);

export function Card({ id, title, subtitle, actions, className, children }: CardProps) {
  const titleId = useId();
  const Heading = useContext(CardHeadingLevel) === 2 ? 'h2' : 'h3';
  const hasHeader = title !== undefined || actions !== undefined;
  return (
    <section
      id={id}
      tabIndex={id === undefined ? undefined : -1}
      aria-labelledby={title === undefined ? undefined : titleId}
      className={cx(
        'rounded-card bg-elevated p-4 text-text shadow-sm',
        // A linked card lands below the sticky top bar; the script-only focus draws no outline.
        id !== undefined && 'scroll-mt-28 focus:outline-none',
        className,
      )}
    >
      {hasHeader && (
        <header className="mb-3 flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
          <div className="min-w-0">
            {title !== undefined && (
              <Heading id={titleId} className="break-words text-base font-medium">
                {title}
              </Heading>
            )}
            {subtitle !== undefined && <p className="text-sm text-text-muted">{subtitle}</p>}
          </div>
          {actions !== undefined && (
            <div className="flex shrink-0 items-center gap-1">{actions}</div>
          )}
        </header>
      )}
      {children}
    </section>
  );
}
