import { render, screen } from '@testing-library/react';
import type { ECElementEvent, EChartsOption } from 'echarts';
import { getInstanceByDom } from 'echarts/core';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { barOption } from './builders/bar';
import { boxplotOption } from './builders/boxplot';
import { bumpOption } from './builders/bump';
import { calendarOption } from './builders/calendar';
import { heatmapOption } from './builders/heatmap';
import { histogramOption } from './builders/histogram';
import { lineOption } from './builders/line';
import { raceOption } from './builders/race';
import { ridgelineOption } from './builders/ridgeline';
import { scatterOption } from './builders/scatter';
import { EChart } from './EChart';
import type { LeaderboardFrame, TabularData } from './types';

const BAR: EChartsOption = {
  xAxis: { type: 'category', data: ['2025', '2026'] },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', name: 'Rounds', data: [1267, 969] }],
};
const LINE: EChartsOption = {
  xAxis: { type: 'category', data: ['a'] },
  yAxis: { type: 'value' },
  series: [{ type: 'line', name: 'Avg', data: [35] }],
};
const ZOOMABLE: EChartsOption = {
  xAxis: { type: 'category', data: ['2023', '2024', '2025', '2026'] },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', name: 'Rounds', data: [1100, 1180, 1267, 969] }],
  dataZoom: [{ type: 'inside' }],
};

function chartOf(): ReturnType<typeof getInstanceByDom> {
  return getInstanceByDom(screen.getByRole('img', { name: 'Rounds by year' }));
}

function clickPoint(dataIndex: number): void {
  chartOf()?.trigger('click', { dataIndex } as unknown as ECElementEvent);
}

const RealResizeObserver = globalThis.ResizeObserver;

afterEach(() => {
  globalThis.ResizeObserver = RealResizeObserver;
});

describe('EChart', () => {
  it('renders an accessible image region with the requested height and the sunday-clays theme', () => {
    render(<EChart option={BAR} height={240} ariaLabel="Rounds by year" />);
    const el = screen.getByRole('img', { name: 'Rounds by year' });
    expect(el).toHaveStyle({ height: '240px' });
    const option = chartOf()?.getOption() as { series: { name: string }[]; color: string[] };
    expect(option.series.map((s) => s.name)).toEqual(['Rounds']);
    expect(option.color[0]).toBe('#E8A77A');
  });

  it('replaces (not merges) the option when it changes', () => {
    const { rerender } = render(<EChart option={BAR} height="50vh" ariaLabel="Rounds by year" />);
    rerender(<EChart option={LINE} height="50vh" ariaLabel="Rounds by year" />);
    const option = chartOf()?.getOption() as { series: { type: string; name: string }[] };
    expect(option.series).toHaveLength(1);
    expect(option.series[0]).toMatchObject({ type: 'line', name: 'Avg' });
    expect(screen.getByRole('img', { name: 'Rounds by year' })).toHaveStyle({ height: '50vh' });
  });

  it('keeps the zoom when re-rendered with an equal option object', () => {
    const { rerender } = render(
      <EChart option={ZOOMABLE} height={200} ariaLabel="Rounds by year" />,
    );
    chartOf()?.dispatchAction({ type: 'dataZoom', start: 50, end: 100 });
    rerender(<EChart option={{ ...ZOOMABLE }} height={200} ariaLabel="Rounds by year" />);
    const option = chartOf()?.getOption() as { dataZoom: { start: number }[] };
    expect(option.dataZoom[0]?.start).toBe(50);
  });

  it('applies an option whose only change is the code of a formatter', () => {
    const { rerender } = render(
      <EChart
        option={{ ...BAR, tooltip: { formatter: () => 'old' } }}
        height={200}
        ariaLabel="Rounds by year"
      />,
    );
    rerender(
      <EChart
        option={{ ...BAR, tooltip: { formatter: () => 'new' } }}
        height={200}
        ariaLabel="Rounds by year"
      />,
    );
    const option = chartOf()?.getOption() as { tooltip: { formatter: () => string }[] };
    expect(option.tooltip[0]?.formatter()).toBe('new');
  });

  it('forwards chart events to onEvents and unbinds them when handlers change', () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = render(
      <EChart option={BAR} height={200} ariaLabel="Rounds by year" onEvents={{ click: first }} />,
    );
    clickPoint(1);
    expect(first).toHaveBeenCalledWith(expect.objectContaining({ dataIndex: 1 }));
    rerender(
      <EChart
        option={BAR}
        height={200}
        ariaLabel="Rounds by year"
        onEvents={{ click: second, dblclick: undefined }}
      />,
    );
    clickPoint(0);
    expect(first).toHaveBeenCalledTimes(1);
    expect(second).toHaveBeenCalledTimes(1);
  });

  it('re-measures its container when it resizes and disposes the chart on unmount', () => {
    let onResize: () => void = () => undefined;
    const disconnect = vi.fn();
    globalThis.ResizeObserver = class {
      constructor(cb: () => void) {
        onResize = cb;
      }
      observe() {}
      unobserve() {}
      disconnect = disconnect;
    } as unknown as typeof ResizeObserver;
    const { unmount } = render(<EChart option={BAR} height={200} ariaLabel="Rounds by year" />);
    const el = screen.getByRole('img', { name: 'Rounds by year' });
    // jsdom lays nothing out, so the chart starts at the 320px fallback width.
    expect(getInstanceByDom(el)?.getWidth()).toBe(320);
    Object.defineProperty(el, 'clientWidth', { configurable: true, value: 640 });
    onResize();
    expect(getInstanceByDom(el)?.getWidth()).toBe(640);
    expect(disconnect).not.toHaveBeenCalled();
    unmount();
    expect(disconnect).toHaveBeenCalledTimes(1);
    expect(getInstanceByDom(el)).toBeUndefined();
  });

  it('unmounts with bound handlers without touching the disposed chart', () => {
    const warn = vi.spyOn(console, 'warn');
    const error = vi.spyOn(console, 'error');
    const { unmount } = render(
      <EChart option={BAR} height={200} ariaLabel="Rounds by year" onEvents={{ click: vi.fn() }} />,
    );
    unmount();
    expect(warn).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalled();
  });

  it('renders every builder option with no ECharts console output, visualMaps continuous', () => {
    const spies = (['log', 'warn', 'error'] as const).map((method) => vi.spyOn(console, method));
    const data: TabularData = {
      columns: [
        { key: 'date', label: 'Event', type: 'date' },
        { key: 'station', label: 'Station', type: 'int' },
        { key: 'shooter', label: 'Shooter', type: 'string' },
        { key: 'score', label: 'Score', type: 'int' },
      ],
      rows: [
        { date: '2026-09-06', station: 1, shooter: 'Able', score: 38 },
        { date: '2026-09-13', station: 2, shooter: 'Baker', score: 41 },
        { date: '2026-09-20', station: 3, shooter: 'Able', score: 35 },
      ],
    };
    const frames: LeaderboardFrame[] = [
      { date: '2026-09-06', rows: [{ id: 1, name: 'Able', value: 38, rank: 1 }] },
      {
        date: '2026-09-13',
        rows: [
          { id: 2, name: 'Baker', value: 41, rank: 1 },
          { id: 1, name: 'Able', value: 38, rank: 2 },
        ],
      },
    ];
    const options: [string, EChartsOption][] = [
      ['line', lineOption(data, { x: 'date', y: ['score'] })],
      ['bar', barOption(data, { x: 'shooter', y: ['score'] })],
      ['scatter', scatterOption(data, { x: 'station', y: 'score', fit: true })],
      ['heatmap', heatmapOption(data, { x: 'station', y: 'shooter', value: 'score' })],
      ['histogram', histogramOption(data, { value: 'score', binWidth: 5 })],
      ['boxplot', boxplotOption(data, { group: 'shooter', value: 'score' })],
      ['calendar', calendarOption(data, { date: 'date', value: 'score', year: 2026 })],
      ['race', raceOption(frames[1] ?? frames[0] ?? { date: '', rows: [] })],
      ['bump', bumpOption(frames)],
      ['ridgeline', ridgelineOption(data, { group: 'shooter', value: 'score' })],
    ];
    type Applied = { series: { type: string }[]; visualMap?: { type: string }[] };
    const applied = new Map<string, Applied>();
    const { rerender } = render(<EChart option={BAR} height={200} ariaLabel="Rounds by year" />);
    for (const [name, option] of options) {
      rerender(<EChart option={option} height={200} ariaLabel="Rounds by year" />);
      applied.set(name, chartOf()?.getOption() as Applied);
    }
    expect([...applied].map(([name, o]) => [name, o.series[0]?.type])).toEqual([
      ['line', 'line'],
      ['bar', 'bar'],
      ['scatter', 'scatter'],
      ['heatmap', 'heatmap'],
      ['histogram', 'bar'],
      ['boxplot', 'boxplot'],
      ['calendar', 'heatmap'],
      ['race', 'bar'],
      ['bump', 'line'],
      ['ridgeline', 'line'],
    ]);
    expect(applied.get('heatmap')?.visualMap?.[0]?.type).toBe('continuous');
    expect(applied.get('calendar')?.visualMap?.[0]?.type).toBe('continuous');
    for (const spy of spies) expect(spy).not.toHaveBeenCalled();
  });
});
