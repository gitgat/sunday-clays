import type { FC } from 'react';
import { describe, expect, it } from 'vitest';
import { collectEventSections, sectionsAt } from './sections';

const Body: FC<{ date: string }> = () => null;

describe('collectEventSections', () => {
  it('keeps modules that export eventSection, sorted by order then id', () => {
    const sections = collectEventSections({
      '../zeta/eventSection.tsx': {
        eventSection: { id: 'zeta', title: 'Zeta', order: 20, Component: Body },
      },
      '../alpha/eventSection.tsx': {
        eventSection: { id: 'alpha', title: 'Alpha', order: 20, Component: Body },
      },
      '../first/eventSection.tsx': {
        eventSection: { id: 'first', title: 'First', order: 5, Component: Body },
      },
      '../broken/eventSection.tsx': {},
    });
    expect(sections.map((s) => s.id)).toEqual(['first', 'alpha', 'zeta']);
  });

  it('returns an empty list when no feature registers a section', () => {
    expect(collectEventSections({})).toEqual([]);
  });
});

describe('sectionsAt', () => {
  it('splits sections by placement, bottom by default', () => {
    const top = {
      id: 'insights',
      title: 'Insights',
      order: 5,
      placement: 'top' as const,
      Component: Body,
    };
    const plain = { id: 'trophies', title: 'Trophies', order: 10, Component: Body };
    expect(sectionsAt([top, plain], 'top')).toEqual([top]);
    expect(sectionsAt([top, plain], 'bottom')).toEqual([plain]);
  });
});
