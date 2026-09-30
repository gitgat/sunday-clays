import type { ReactNode } from 'react';

/**
 * The shared EmptyState's layout with a caller-chosen heading level. EmptyState is always an h3,
 * which fits inside a titled card (h2) but skips a level directly under a page's h1.
 */
export function Notice({
  level,
  title,
  children,
}: {
  level: 1 | 2;
  title: string;
  children?: ReactNode;
}) {
  const Heading = level === 1 ? 'h1' : 'h2';
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
      <Heading className={level === 1 ? 'text-2xl font-medium' : 'text-base font-medium'}>
        {title}
      </Heading>
      {children !== undefined && <p className="max-w-prose text-sm text-text-muted">{children}</p>}
    </div>
  );
}
