import { describe, expect, it } from 'vitest';
import { chartPalette } from '../../../theme/tokens';
import type { TabularData } from '../types';
import { barOption } from './bar';
import { boxplotOption } from './boxplot';
import {
  axisTypeFor,
  cellLabel,
  distinct,
  escapeHtml,
  legendFor,
  numeric,
  GRID,
  NAME_BELOW,
  paletteColor,
  requireColumn,
} from './common';
import { heatmapOption } from './heatmap';
import { histogramOption } from './histogram';
import { lineOption } from './line';
import { ridgelineOption } from './ridgeline';
import { scatterOption } from './scatter';

const DATA: TabularData = { columns: [{ key: 'year', label: 'Year', type: 'int' }], rows: [] };

describe('builder helpers', () => {
  it('escapes HTML in data-derived strings', () => {
    expect(escapeHtml('<img src=x onerror=alert(1)>')).toBe('&lt;img src=x onerror=alert(1)&gt;');
  });

  it('throws a clear error for an unknown column', () => {
    expect(requireColumn(DATA, 'year').label).toBe('Year');
    expect(() => requireColumn(DATA, 'nope')).toThrow('Unknown column "nope"');
  });

  it('maps column types to axis types', () => {
    expect(axisTypeFor({ key: 'd', label: 'D', type: 'date' })).toBe('time');
    expect(axisTypeFor({ key: 's', label: 'S', type: 'string' })).toBe('category');
    expect(axisTypeFor({ key: 'n', label: 'N', type: 'number' })).toBe('value');
    expect(axisTypeFor({ key: 'i', label: 'I', type: 'int' })).toBe('value');
  });

  it('keeps only finite numbers and labels missing cells with a dash', () => {
    expect([
      numeric(3),
      numeric('3'),
      numeric(null),
      numeric(Number.NaN),
      numeric(undefined),
    ]).toEqual([3, null, null, null, null]);
    expect([cellLabel(null), cellLabel(undefined), cellLabel(2026), cellLabel('A')]).toEqual([
      '—',
      '—',
      '2026',
      'A',
    ]);
  });

  it('dedupes in first-appearance order and shows a legend only for several series', () => {
    expect(distinct(['b', 'a', 'b'])).toEqual(['b', 'a']);
    expect(legendFor(1)).toEqual({ show: false });
    expect(legendFor(2)).toEqual({ type: 'scroll', top: 0 });
  });

  it('picks palette colors by index, wrapping both ways, with the first color for a non-integer', () => {
    expect(paletteColor(0)).toBe(chartPalette[0]);
    expect(paletteColor(chartPalette.length + 1)).toBe(chartPalette[1]);
    expect(paletteColor(-1)).toBe(chartPalette[chartPalette.length - 1]);
    expect(paletteColor(1.5)).toBe(chartPalette[0]);
    expect(paletteColor(Number.NaN)).toBe(chartPalette[0]);
  });

  it('freezes GRID, and every builder hands out its own copy for a chart to adjust', () => {
    expect(Object.isFrozen(GRID)).toBe(true);
    const xy: TabularData = {
      columns: [
        { key: 'x', label: 'X', type: 'number' },
        { key: 'y', label: 'Y', type: 'number' },
      ],
      rows: [{ x: 1, y: 2 }],
    };
    const grids = [
      lineOption(xy, { x: 'x', y: ['y'] }),
      barOption(xy, { x: 'x', y: ['y'] }),
      scatterOption(xy, { x: 'x', y: 'y' }),
      histogramOption(xy, { value: 'y', binWidth: 1 }),
      boxplotOption(xy, { group: 'x', value: 'y' }),
    ].map((o) => o.grid as typeof GRID);
    for (const grid of grids) {
      expect(grid).toEqual(GRID);
      expect(grid).not.toBe(GRID);
    }
    (grids[0] as { left: number }).left = 99;
    expect(GRID.left).toBe(8);
    expect(grids[1]?.left).toBe(8);
  });

  it('keeps axis names, not just tick labels, inside the grid, below the legend and toolbox row', () => {
    // 'axisLabel' left every axis name outside the canvas edge (x names under the axis, a
    // heatmap's end-of-axis name); 'all' shrinks the plot until labels and names fit.
    expect(GRID).toMatchObject({ outerBoundsMode: 'same', outerBoundsContain: 'all', top: 32 });
  });

  it('names every x axis centred below its tick labels', () => {
    expect(NAME_BELOW).toEqual({ nameLocation: 'middle', nameGap: 28 });
    const xy: TabularData = {
      columns: [
        { key: 'g', label: 'G', type: 'string' },
        { key: 'x', label: 'X', type: 'number' },
        { key: 'y', label: 'Y', type: 'number' },
      ],
      rows: [{ g: 'a', x: 1, y: 2 }],
    };
    const xAxes = [
      lineOption(xy, { x: 'x', y: ['y'] }),
      scatterOption(xy, { x: 'x', y: 'y' }),
      histogramOption(xy, { value: 'y', binWidth: 1 }),
      ridgelineOption(xy, { group: 'g', value: 'y' }),
      heatmapOption(xy, { x: 'g', y: 'x', value: 'y' }),
      barOption(xy, { x: 'g', y: ['y'], horizontal: true }),
    ].map((o) => o.xAxis);
    for (const axis of xAxes) expect(axis).toMatchObject(NAME_BELOW);
  });
});
