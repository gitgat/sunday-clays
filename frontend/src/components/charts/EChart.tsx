import type { EChartsOption, ECElementEvent } from 'echarts';
import { BarChart, BoxplotChart, HeatmapChart, LineChart, ScatterChart } from 'echarts/charts';
import {
  CalendarComponent,
  DataZoomComponent,
  GraphicComponent,
  GridComponent,
  LegendComponent,
  ToolboxComponent,
  TooltipComponent,
  VisualMapContinuousComponent,
} from 'echarts/components';
// `use` is aliased so eslint's rules-of-hooks does not mistake it for React's use().
import { init, registerTheme, use as registerModules, type EChartsType } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { useEffect, useRef } from 'react';
import { ECHARTS_THEME_NAME, echartsTheme } from '../../theme/echartsTheme';

// Only what the C10 builders use, so the charts chunk stays small.
registerModules([
  BarChart,
  BoxplotChart,
  HeatmapChart,
  LineChart,
  ScatterChart,
  CalendarComponent,
  DataZoomComponent,
  GraphicComponent,
  GridComponent,
  LegendComponent,
  ToolboxComponent,
  TooltipComponent,
  VisualMapContinuousComponent,
  CanvasRenderer,
]);
registerTheme(ECHARTS_THEME_NAME, echartsTheme);

export type EChartEventName = 'click' | 'dblclick' | 'mouseover' | 'mouseout';
export type EChartEvents = {
  [K in EChartEventName]?: ((params: ECElementEvent) => void) | undefined;
};

export interface EChartProps {
  option: EChartsOption;
  /** CSS height; a number is px. */
  height: number | string;
  onEvents?: EChartEvents | undefined;
  ariaLabel: string;
}

/**
 * Content key of an option: JSON with every function replaced by its source text. Formatters
 * must read only values that are also in the option (every C10 builder does), because two
 * closures with the same source text compare equal.
 */
function optionKey(option: EChartsOption): string {
  return JSON.stringify(option, (_key, value: unknown) =>
    typeof value === 'function' ? String(value) : value,
  );
}

/**
 * Thin ECharts wrapper (C10). Data charts render inside ChartFrame/ChartCard, never bare.
 * An option object with the same content as the last one applied is skipped, so a parent
 * re-render (any URL change) never resets the user's zoom or replays the entry animation.
 */
export function EChart({ option, height, onEvents, ariaLabel }: EChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const lastKey = useRef<string | null>(null);
  const initialHeight = useRef(height);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    // Explicit size so a not-yet-laid-out (or hidden) container never initializes at 0×0.
    const chart = init(el, ECHARTS_THEME_NAME, {
      renderer: 'canvas',
      width: el.clientWidth || 320,
      height:
        el.clientHeight ||
        (typeof initialHeight.current === 'number' ? initialHeight.current : 320),
    });
    chartRef.current = chart;
    // 'auto' re-measures the container; a bare resize() keeps the explicit init size forever.
    const observer = new ResizeObserver(() => chart.resize({ width: 'auto', height: 'auto' }));
    observer.observe(el);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
      lastKey.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const key = optionKey(option);
    if (key === lastKey.current) return;
    lastKey.current = key;
    chart.setOption(option, { notMerge: true });
  }, [option]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !onEvents) return;
    const bound: [EChartEventName, (params: ECElementEvent) => void][] = [];
    for (const name of Object.keys(onEvents) as EChartEventName[]) {
      const handler = onEvents[name];
      if (handler) {
        chart.on(name, handler);
        bound.push([name, handler]);
      }
    }
    return () => {
      // On unmount the init effect's cleanup has already disposed the chart (and its handlers).
      if (chart.isDisposed()) return;
      for (const [name, handler] of bound) chart.off(name, handler);
    };
  }, [onEvents]);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label={ariaLabel}
      style={{ height: typeof height === 'number' ? `${height}px` : height, width: '100%' }}
    />
  );
}
