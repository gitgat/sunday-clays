import { expect, it } from 'vitest';
import {
  hollowPoint,
  hollowSeries,
  THROWN_OUT_COLUMN,
  thrownOutAxisTooltip,
  thrownOutCell,
} from './thrownOut';

it('names the CSV column', () => {
  expect(THROWN_OUT_COLUMN).toEqual({ key: 'thrown_out', label: 'Thrown out', type: 'string' });
});

it('marks a thrown-out row yes, others blank', () => {
  expect(thrownOutCell(true)).toBe('yes');
  expect(thrownOutCell(false)).toBe('');
});

it('makes only thrown-out points hollow', () => {
  expect(hollowPoint(43, true)).toEqual({ value: 43, symbol: 'emptyCircle', symbolSize: 8 });
  expect(hollowPoint(43, false)).toBe(43);
});

it('hollows the named series at the flagged indices only, without mutating', () => {
  const option = {
    series: [
      { name: 'A', type: 'line', data: [1, 2] },
      { name: 'B', type: 'line', data: [3, 4] },
    ],
  };
  expect(hollowSeries(option, ['A'], [false, true]).series).toEqual([
    { name: 'A', type: 'line', data: [1, { value: 2, symbol: 'emptyCircle', symbolSize: 8 }] },
    { name: 'B', type: 'line', data: [3, 4] },
  ]);
  expect(option.series[0]?.data).toEqual([1, 2]);
});

it('stars the tooltip header of a thrown-out date, on category and time axes', () => {
  const f = thrownOutAxisTooltip(new Set(['2026-10-25']));
  expect(
    f([
      {
        axisValue: '2026-10-25',
        axisValueLabel: '2026-10-25',
        marker: '',
        seriesName: 'Score',
        value: 43,
      },
    ]),
  ).toBe('2026-10-25 *<br/>Score: 43');
  expect(
    f([
      {
        axisValue: '2026-10-04',
        axisValueLabel: '2026-10-04',
        marker: '',
        seriesName: 'Score',
        value: 40,
      },
    ]),
  ).toBe('2026-10-04<br/>Score: 40');
  expect(
    f([
      {
        axisValue: Date.UTC(2026, 9, 25),
        axisValueLabel: 'Oct 25',
        marker: '',
        seriesName: 'Middle score',
        value: ['2026-10-25', 34],
      },
      {
        axisValue: Date.UTC(2026, 9, 25),
        axisValueLabel: 'Oct 25',
        marker: '',
        seriesName: 'Top score',
        value: ['2026-10-25', null],
      },
    ]),
  ).toBe('Oct 25 *<br/>Middle score: 34');
});

it('leaves an option without a series array untouched', () => {
  expect(hollowSeries({}, ['A'], [true])).toEqual({ series: [] });
  expect(hollowSeries({ series: { name: 'A', data: [1] } }, ['A'], [true]).series).toEqual([]);
});

it('returns an empty tooltip when there are no axis params', () => {
  expect(thrownOutAxisTooltip(new Set(['2026-10-25']))([])).toBe('');
});

it('omits the marker when ECharts supplies none', () => {
  const f = thrownOutAxisTooltip(new Set<string>());
  expect(
    f([{ axisValue: '2026-10-04', axisValueLabel: '2026-10-04', seriesName: 'Score', value: 40 }]),
  ).toBe('2026-10-04<br/>Score: 40');
});
