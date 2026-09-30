import { chartPalette, colors, fontFamily, gridLine } from './tokens';

export const ECHARTS_THEME_NAME = 'sunday-clays';

/** Accent at low opacity: dataZoom window fill and brush. */
const accentWash = (alpha: number) => `rgba(232, 167, 122, ${alpha})`;

const axis = {
  axisLine: { lineStyle: { color: colors.outlineVariant } },
  axisTick: { lineStyle: { color: colors.outlineVariant } },
  axisLabel: { color: colors.textMuted },
  splitLine: { lineStyle: { color: gridLine } },
  // Alternating bands (when a chart turns splitArea on): clear, then a faint outline tint.
  splitArea: { areaStyle: { color: ['transparent', 'rgba(209, 231, 218, 0.04)'] } },
  nameTextStyle: { color: colors.textMuted },
};

/** ECharts theme registered by EChart.tsx under ECHARTS_THEME_NAME. */
export const echartsTheme = {
  color: [...chartPalette],
  backgroundColor: 'transparent',
  textStyle: { fontFamily, color: colors.textMuted },
  title: { textStyle: { color: colors.text }, subtextStyle: { color: colors.textMuted } },
  legend: { textStyle: { color: colors.text } },
  tooltip: {
    backgroundColor: colors.elevated,
    borderColor: colors.outlineVariant,
    textStyle: { color: colors.text },
  },
  categoryAxis: axis,
  valueAxis: axis,
  timeAxis: axis,
  logAxis: axis,
  dataZoom: {
    borderColor: colors.outlineVariant,
    fillerColor: accentWash(0.2),
    dataBackground: {
      lineStyle: { color: colors.outlineVariant },
      areaStyle: { color: colors.outlineVariant },
    },
    selectedDataBackground: {
      lineStyle: { color: colors.accent },
      areaStyle: { color: colors.accent },
    },
    handleStyle: { color: colors.accent, borderColor: colors.accent },
    moveHandleStyle: { color: colors.outlineVariant },
    brushStyle: { color: accentWash(0.15) },
    emphasis: {
      handleStyle: { borderColor: colors.outline },
      moveHandleStyle: { color: colors.accent },
    },
    textStyle: { color: colors.textMuted },
  },
  // The low end must differ from cards (elevated) and the page (surface), or minimum cells vanish.
  visualMap: { inRange: { color: [colors.outlineVariant, colors.accent] } },
  toolbox: {
    iconStyle: { borderColor: colors.textMuted },
    emphasis: { iconStyle: { borderColor: colors.accent } },
  },
  markLine: { lineStyle: { color: colors.outline } },
};
