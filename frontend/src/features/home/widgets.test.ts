import type { FC } from 'react';
import { describe, expect, it } from 'vitest';
import { collectHomeWidgets, widgetsForSlot } from './widgets';

const W: FC<{ meId: number | null }> = () => null;

describe('home widgets', () => {
  const widgets = collectHomeWidgets({
    '../predictions/homeWidget.tsx': {
      homeWidget: { id: 'next-sunday', order: 10, slot: 'main', Component: W },
    },
    '../achievements/homeWidget.tsx': {
      homeWidget: { id: 'next-trophy', order: 10, slot: 'me', Component: W },
    },
    '../fake/homeWidget.tsx': {
      homeWidget: { id: 'fake-main', order: 5, slot: 'main', Component: W },
    },
    '../other/homeWidget.tsx': {},
  });

  it('collects exported widgets sorted by order then id', () => {
    expect(widgets.map((w) => w.id)).toEqual(['fake-main', 'next-sunday', 'next-trophy']);
  });

  it('filters widgets by slot, keeping the order', () => {
    expect(widgetsForSlot(widgets, 'main').map((w) => w.id)).toEqual(['fake-main', 'next-sunday']);
    expect(widgetsForSlot(widgets, 'me').map((w) => w.id)).toEqual(['next-trophy']);
  });
});
