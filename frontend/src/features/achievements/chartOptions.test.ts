import { describe, expect, it } from 'vitest';
import {
  cumulativeByDate,
  cumulativeLineOption,
  percentFormatter,
  rarityBarOption,
} from './chartOptions';

describe('rarityBarOption', () => {
  it('plots one bar per trophy in its metal colour', () => {
    const option = rarityBarOption([
      { label: 'Clays Broken — 1,000 clays broken', rarityPct: 19.6, color: '#C9D1D6' },
      { label: 'First Win', rarityPct: 36.1, color: '#E8A77A' },
    ]);
    expect(option.yAxis).toMatchObject({
      type: 'category',
      data: ['Clays Broken — 1,000 clays broken', 'First Win'],
    });
    expect(option.series).toEqual([
      expect.objectContaining({
        type: 'bar',
        data: [
          { value: 19.6, itemStyle: { color: '#C9D1D6' } },
          { value: 36.1, itemStyle: { color: '#E8A77A' } },
        ],
      }),
    ]);
    expect(option.tooltip).not.toHaveProperty('formatter');
  });
});

describe('percentFormatter', () => {
  it('formats numbers and falls back to a dash', () => {
    expect(percentFormatter(12.345)).toBe('12.35%');
    expect(percentFormatter('x')).toBe('—');
  });
});

describe('cumulativeByDate', () => {
  it('counts per date and accumulates in date order', () => {
    expect(cumulativeByDate(['2025-01-12', '2025-01-05', '2025-01-12'])).toEqual([
      { date: '2025-01-05', total: 1 },
      { date: '2025-01-12', total: 3 },
    ]);
  });
});

describe('cumulativeLineOption', () => {
  it('draws a step line over time', () => {
    const option = cumulativeLineOption([{ date: '2025-01-05', total: 1 }], 'Holders');
    expect(option.xAxis).toMatchObject({ type: 'time' });
    expect(option.series).toEqual([
      expect.objectContaining({
        type: 'line',
        name: 'Holders',
        step: 'end',
        data: [['2025-01-05', 1]],
      }),
    ]);
  });
});
