import type { EChartsOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import { defaultZoom, withZoom } from './zoom';

const CARTESIAN: EChartsOption = {
  xAxis: { type: 'category' },
  yAxis: { type: 'value' },
  series: [],
};
/** Categories down the y axis (e.g. shooters), values along x. */
const HORIZONTAL: EChartsOption = {
  xAxis: { type: 'value' },
  yAxis: { type: 'category' },
  series: [],
};

describe('withZoom initial window', () => {
  it('copies a start and end value from the option dataZoom onto inside and slider', () => {
    const o = withZoom(
      { ...CARTESIAN, dataZoom: [{ type: 'inside', startValue: 3, endValue: 9 }] },
      'x',
      false,
    );
    expect(o.dataZoom).toMatchObject([
      { type: 'inside', startValue: 3, endValue: 9 },
      { type: 'slider', startValue: 3, endValue: 9 },
    ]);
  });

  it('copies a start value alone, and reads a single (non-array) dataZoom', () => {
    const o = withZoom({ ...CARTESIAN, dataZoom: { type: 'inside', startValue: 3 } }, 'x', true);
    expect(o.dataZoom).toEqual([
      { type: 'inside', zoomOnMouseWheel: 'shift', moveOnMouseMove: false, startValue: 3 },
    ]);
  });

  it('carries the window onto the category (y) zoom too', () => {
    const o = withZoom(
      { ...HORIZONTAL, dataZoom: [{ type: 'inside', startValue: 1, endValue: 2 }] },
      'y',
      false,
    );
    expect(o.dataZoom).toMatchObject([
      { yAxisIndex: 0, startValue: 1, endValue: 2 },
      { yAxisIndex: 0, startValue: 1, endValue: 2 },
    ]);
  });

  it('adds nothing when the option names no window', () => {
    const o = withZoom({ ...CARTESIAN, dataZoom: [{ type: 'inside' }] }, 'x', false);
    expect(JSON.stringify(o.dataZoom)).not.toContain('startValue');
  });
});

describe('withZoom', () => {
  it("adds inside + slider zoom along x for 'x' on a pointer device", () => {
    const o = withZoom(CARTESIAN, 'x', false);
    expect(o.dataZoom).toEqual([
      { type: 'inside', zoomOnMouseWheel: 'shift', moveOnMouseMove: true },
      { type: 'slider', height: 18, bottom: 4 },
    ]);
    expect(o.toolbox).toMatchObject({ feature: { dataZoom: { yAxisIndex: 'none' }, restore: {} } });
    // In the legend row above the grid (GRID.top 32): ECharts 6's default padding of 15 would
    // drop the icons onto the top of the plot.
    expect(o.toolbox).toMatchObject({ right: 8, top: 0, padding: 4 });
    expect(o.series).toBe(CARTESIAN.series);
  });

  it('never pans on one-finger drag and drops the slider on touch', () => {
    const o = withZoom(CARTESIAN, 'x', true);
    expect(o.dataZoom).toEqual([
      { type: 'inside', zoomOnMouseWheel: 'shift', moveOnMouseMove: false },
    ]);
  });

  it("lets the toolbox box-zoom both axes for 'xy'", () => {
    const o = withZoom(CARTESIAN, 'xy', false) as {
      toolbox: { feature: { dataZoom: { yAxisIndex?: unknown } } };
    };
    expect(o.toolbox.feature.dataZoom.yAxisIndex).toBeUndefined();
  });

  it("returns the option untouched for 'none'", () => {
    expect(withZoom(CARTESIAN, 'none', false)).toBe(CARTESIAN);
  });

  it('lifts the grid and a bottom visualMap clear of the slider, copying frozen input', () => {
    const grid = Object.freeze({ left: 8, bottom: 48 });
    const visualMap = Object.freeze({ type: 'continuous' as const, bottom: 0 });
    const heat: EChartsOption = Object.freeze({ ...CARTESIAN, grid, visualMap });
    const o = withZoom(heat, 'x', false);
    // The slider takes the bottom 22 px (height 18 + bottom 4), so axis labels and the
    // visualMap legend move up by that much instead of being drawn over.
    expect(o.grid).toEqual({ left: 8, bottom: 70 });
    expect(o.visualMap).toEqual({ type: 'continuous', bottom: 22 });
    expect(grid).toEqual({ left: 8, bottom: 48 });
    expect(visualMap).toEqual({ type: 'continuous', bottom: 0 });
  });

  it('keeps the layout without a slider (touch) or without a numeric bottom', () => {
    const touch: EChartsOption = { ...CARTESIAN, grid: { bottom: 8 } };
    expect(withZoom(touch, 'x', true).grid).toBe(touch.grid);
    const other: EChartsOption = { ...CARTESIAN, grid: { bottom: '10%' }, visualMap: [] };
    expect(withZoom(other, 'x', false).grid).toBe(other.grid);
    expect(withZoom(other, 'x', false).visualMap).toBe(other.visualMap);
    // No grid: ECharts' default grid (bottom 80) already leaves room for the slider.
    expect(withZoom(CARTESIAN, 'x', false)).not.toHaveProperty('grid');
    expect(withZoom(CARTESIAN, 'x', false)).not.toHaveProperty('visualMap');
  });

  it("zooms the category (y) axis for 'y', with the slider on the right, copying frozen input", () => {
    const grid = Object.freeze({ right: 24, bottom: 8 });
    const visualMap = Object.freeze({ type: 'continuous' as const, bottom: 0 });
    const bars: EChartsOption = Object.freeze({ ...HORIZONTAL, grid, visualMap });
    const o = withZoom(bars, 'y', false);
    expect(o.dataZoom).toEqual([
      { type: 'inside', yAxisIndex: 0, zoomOnMouseWheel: 'shift', moveOnMouseMove: true },
      { type: 'slider', yAxisIndex: 0, width: 18, right: 4 },
    ]);
    expect(o.toolbox).toMatchObject({
      right: 8,
      top: 0,
      padding: 4,
      feature: { dataZoom: { xAxisIndex: 'none' }, restore: {} },
    });
    // The slider takes the right 22 px, so the grid moves in from the right, not up.
    expect(o.grid).toEqual({ right: 46, bottom: 8 });
    expect(o.visualMap).toBe(visualMap);
    expect(grid).toEqual({ right: 24, bottom: 8 });
    const touch = withZoom(bars, 'y', true);
    expect(touch.dataZoom).toEqual([
      { type: 'inside', yAxisIndex: 0, zoomOnMouseWheel: 'shift', moveOnMouseMove: false },
    ]);
    expect(touch.grid).toBe(grid);
  });
});

describe('defaultZoom', () => {
  it('zooms x on charts with both axes, not on calendars or axis-less charts', () => {
    expect(defaultZoom(CARTESIAN)).toBe('x');
    expect(defaultZoom({ ...CARTESIAN, calendar: {} })).toBe('none');
    expect(defaultZoom({ series: [] })).toBe('none');
  });

  it('zooms y on horizontal bars (categories on y), x when both axes are categories', () => {
    expect(defaultZoom(HORIZONTAL)).toBe('y');
    expect(defaultZoom({ xAxis: [{ type: 'value' }], yAxis: [{ type: 'category' }] })).toBe('y');
    expect(defaultZoom({ xAxis: { type: 'category' }, yAxis: { type: 'category' } })).toBe('x');
    expect(defaultZoom({ xAxis: {}, yAxis: {} })).toBe('x');
    expect(defaultZoom({ xAxis: [], yAxis: [] })).toBe('x');
  });
});
