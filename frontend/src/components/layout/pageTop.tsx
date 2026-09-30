import type { FC } from 'react';

/** Pages with a top slot for feature content (Plan 12 extension point). */
export type PageKey = 'club' | 'leaderboards' | 'records' | 'stations';

/**
 * Extension point: a feature exports `pageTop` from `src/features/<name>/pageTop.tsx` to render
 * under a page's title, above its own content, on the listed pages.
 */
export type PageTop = {
  id: string;
  order: number;
  pages: readonly PageKey[];
  Component: FC<{ page: PageKey }>;
};

type PageTopModule = { pageTop?: PageTop };

export function collectPageTops(modules: Record<string, PageTopModule>): PageTop[] {
  return Object.values(modules)
    .flatMap((m) => (m.pageTop ? [m.pageTop] : []))
    .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
}

export const pageTops: PageTop[] = collectPageTops(
  import.meta.glob<PageTopModule>('../../features/*/pageTop.tsx', { eager: true }),
);

/** Renders the page's top-slot entries in order (each renders its own card, or nothing). */
export function PageTopSlot({ page, entries = pageTops }: { page: PageKey; entries?: PageTop[] }) {
  return (
    <>
      {entries
        .filter((entry) => entry.pages.includes(page))
        .map(({ id, Component }) => (
          <Component key={id} page={page} />
        ))}
    </>
  );
}
