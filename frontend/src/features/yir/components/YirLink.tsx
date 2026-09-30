import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { useRoundTypeLink } from '../../../lib/roundTypes';

/** An in-app link that keeps the global filters (`rt`), underlined with a 44 px tap target. */
export function YirLink({
  to,
  className = '',
  'aria-current': ariaCurrent,
  children,
}: {
  to: string;
  className?: string;
  'aria-current'?: 'page' | undefined;
  children: ReactNode;
}) {
  return (
    <Link
      to={useRoundTypeLink(to)}
      aria-current={ariaCurrent}
      className={`inline-flex min-h-11 items-center underline ${className}`}
    >
      {children}
    </Link>
  );
}
