import { render, screen } from '@testing-library/react';
import type { FC } from 'react';
import { describe, expect, it } from 'vitest';
import { collectPageTops, PageTopSlot, type PageKey } from './pageTop';

const Named: (text: string) => FC<{ page: PageKey }> = (text) =>
  function Entry({ page }) {
    return (
      <p>
        {text} on {page}
      </p>
    );
  };

describe('collectPageTops', () => {
  it('keeps modules that export pageTop, sorted by order then id', () => {
    const entries = collectPageTops({
      '../b/pageTop.tsx': {
        pageTop: { id: 'b', order: 2, pages: ['club'], Component: Named('b') },
      },
      '../a/pageTop.tsx': {
        pageTop: { id: 'a', order: 2, pages: ['club'], Component: Named('a') },
      },
      '../c/pageTop.tsx': {
        pageTop: { id: 'c', order: 1, pages: ['club'], Component: Named('c') },
      },
      '../d/pageTop.tsx': {},
    });
    expect(entries.map((e) => e.id)).toEqual(['c', 'a', 'b']);
  });
});

describe('PageTopSlot', () => {
  it('renders only the entries for its page', () => {
    render(
      <PageTopSlot
        page="records"
        entries={[
          { id: 'x', order: 1, pages: ['records', 'club'], Component: Named('insights') },
          { id: 'y', order: 2, pages: ['club'], Component: Named('club only') },
        ]}
      />,
    );
    expect(screen.getByText('insights on records')).toBeInTheDocument();
    expect(screen.queryByText(/club only/)).toBeNull();
  });
});
