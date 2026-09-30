import type { FC } from 'react';
import { describe, expect, it } from 'vitest';
import { collectProfileSections, sectionsAt } from './sections';

const Body: FC<{ shooterId: number }> = () => null;

describe('collectProfileSections', () => {
  it('keeps modules that export profileSection, sorted by order then id', () => {
    const sections = collectProfileSections({
      '../weather/profileSection.tsx': {
        profileSection: { id: 'weather', title: 'Weather', order: 30, Component: Body },
      },
      '../achievements/profileSection.tsx': {
        profileSection: { id: 'achievements', title: 'Trophy case', order: 10, Component: Body },
      },
      '../stations/profileSection.tsx': {
        profileSection: { id: 'stations', title: 'Stations', order: 30, Component: Body },
      },
      '../other/profileSection.tsx': {},
    });
    expect(sections.map((s) => s.id)).toEqual(['achievements', 'stations', 'weather']);
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
