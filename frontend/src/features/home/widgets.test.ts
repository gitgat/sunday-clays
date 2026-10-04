import type { FC } from 'react';
import { describe, expect, it } from 'vitest';
import { collectHomeWidgets, homeWidgets, widgetsForSlot } from './widgets';

const W: FC<{ meId: number | null }> = () => null;

describe('home widgets', () => {
  const widgets = collectHomeWidgets({
    '../predictions/homeWidget.tsx': {
      homeWidget: { id: 'next-sunday', order: 10, slot: 'main', Component: W },
    },
    '../achievements/homeWidget.tsx': {
      homeWidget: { id: 'next-trophy', order: 10, slot: 'me', Component: W },
    },
    '../yir/homeWidget.tsx': {
      homeWidget: { id: 'on-this-day', order: 5, slot: 'main', Component: W },
    },
    '../other/homeWidget.tsx': {},
  });

  it('collects exported widgets sorted by order then id', () => {
    expect(widgets.map((w) => w.id)).toEqual(['on-this-day', 'next-sunday', 'next-trophy']);
  });

  it('filters widgets by slot, keeping the order', () => {
    expect(widgetsForSlot(widgets, 'main').map((w) => w.id)).toEqual([
      'on-this-day',
      'next-sunday',
    ]);
    expect(widgetsForSlot(widgets, 'me').map((w) => w.id)).toEqual(['next-trophy']);
  });

  it('test_home_widget_after_next_sunday: Coming up sits between Next Sunday and On this day', () => {
    const main = widgetsForSlot(homeWidgets, 'main').map((w) => w.id);
    expect(main.indexOf('next-sunday')).toBeGreaterThanOrEqual(0);
    expect(main.indexOf('next-sunday')).toBeLessThan(main.indexOf('club-events-next'));
    expect(main.indexOf('club-events-next')).toBeLessThan(main.indexOf('club-milestone'));
    expect(main.indexOf('club-events-next')).toBeLessThan(main.indexOf('on-this-day'));
    expect(homeWidgets.find((w) => w.id === 'club-events-next')).toMatchObject({
      order: 15,
      slot: 'main',
    });
    expect(homeWidgets.find((w) => w.id === 'insights')?.slot).toBe('hero');
  });
});
