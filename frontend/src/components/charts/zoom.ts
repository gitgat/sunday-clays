import type { EChartsOption } from 'echarts';

/**
 * 'x' zooms the x axis; 'xy' also lets the toolbox box-zoom y; 'y' zooms the y axis only, for
 * horizontal bars whose categories (e.g. shooters) run down the y axis.
 */
export type ZoomMode = 'x' | 'xy' | 'y' | 'none';

/** The strip the slider (18 px thick, 4 px off the chart edge) takes along its edge. */
const SLIDER_ROOM = 18 + 4;

/**
 * A copy of a grid or visualMap moved in from `edge` by SLIDER_ROOM, so the slider never covers
 * axis labels, axis names or a legend. Without a numeric offset on that edge (arrays,
 * percentages) it is returned as-is. Builder output may be frozen or shared: never mutate it.
 */
function clearOfSlider<T>(component: T, edge: 'bottom' | 'right'): T {
  const offset = (component as Partial<Record<typeof edge, unknown>>)[edge];
  return typeof offset === 'number' ? { ...component, [edge]: offset + SLIDER_ROOM } : component;
}

/**
 * Box-zoom and restore buttons, in the legend row above the grid (GRID.top): ECharts 6's default
 * padding of 15 would drop the icons onto the top of the plot. `dataZoom` names the axis the box
 * leaves alone ({} = zoom both).
 */
function zoomToolbox(dataZoom: { xAxisIndex?: 'none'; yAxisIndex?: 'none' }) {
  return { right: 8, top: 0, padding: 4, feature: { dataZoom, restore: {} } };
}

/** The initial `startValue`/`endValue` a builder (zoomToWindow) put on the option's own dataZoom. */
function initialWindow(option: EChartsOption): {
  startValue?: string | number;
  endValue?: string | number;
} {
  const own: unknown[] = [option.dataZoom].flat();
  const found = own.find(
    (z) => (z as { startValue?: unknown } | undefined)?.startValue !== undefined,
  ) as { startValue: string | number; endValue?: string | number } | undefined;
  if (found === undefined) return {};
  return found.endValue === undefined
    ? { startValue: found.startValue }
    : { startValue: found.startValue, endValue: found.endValue };
}

/**
 * Box/pinch zoom for cartesian charts (C10): an inside dataZoom (mouse wheel zooms only with
 * Shift; drag pans except on touch, where one-finger drag must scroll the page), a slider on
 * non-touch devices, and toolbox zoom/restore buttons. 'none' returns the option unchanged. An
 * initial window already on the option's dataZoom (zoomToWindow) carries over to both.
 */
export function withZoom(option: EChartsOption, mode: ZoomMode, isTouch: boolean): EChartsOption {
  if (mode === 'none') return option;
  const { grid, visualMap } = option;
  const initial = initialWindow(option);
  if (mode === 'y') {
    // The category axis is y: zoom and scroll it, with the slider down the right-hand side.
    return {
      ...option,
      ...(!isTouch && grid !== undefined ? { grid: clearOfSlider(grid, 'right') } : {}),
      dataZoom: [
        {
          type: 'inside',
          yAxisIndex: 0,
          zoomOnMouseWheel: 'shift',
          moveOnMouseMove: !isTouch,
          ...initial,
        },
        ...(isTouch
          ? []
          : [{ type: 'slider' as const, yAxisIndex: 0, width: 18, right: 4, ...initial }]),
      ],
      toolbox: zoomToolbox({ xAxisIndex: 'none' }),
    };
  }
  return {
    ...option,
    ...(!isTouch && grid !== undefined ? { grid: clearOfSlider(grid, 'bottom') } : {}),
    ...(!isTouch && visualMap !== undefined
      ? { visualMap: clearOfSlider(visualMap, 'bottom') }
      : {}),
    dataZoom: [
      { type: 'inside', zoomOnMouseWheel: 'shift', moveOnMouseMove: !isTouch, ...initial },
      ...(isTouch ? [] : [{ type: 'slider' as const, height: 18, bottom: 4, ...initial }]),
    ],
    toolbox: zoomToolbox(mode === 'x' ? { yAxisIndex: 'none' } : {}),
  };
}

/** The type of an axis option, or of the first axis when there are several. */
function axisType(axis: unknown): unknown {
  const first: unknown = Array.isArray(axis) ? axis[0] : axis;
  return (first as { type?: unknown } | undefined)?.type;
}

/**
 * Charts with both axes zoom along x by default, except horizontal bars (categories on y, values
 * on x), which zoom along their categories; calendars and axis-less charts do not zoom.
 */
export function defaultZoom(option: EChartsOption): ZoomMode {
  if (option.xAxis === undefined || option.yAxis === undefined || option.calendar !== undefined) {
    return 'none';
  }
  return axisType(option.yAxis) === 'category' && axisType(option.xAxis) !== 'category' ? 'y' : 'x';
}
