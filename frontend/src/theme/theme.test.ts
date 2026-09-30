import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { contrast, TOKEN_BY_CLASS_NAME } from '../test/contrast';
import { echartsTheme } from './echartsTheme';
import { chartPalette, colors, fontFamily, radii } from './tokens';

/** Read from disk: Vitest blanks CSS modules (even `?raw`) unless `test.css` includes them. */
const themeCss = readFileSync(join(import.meta.dirname, 'theme.css'), 'utf8');

/** Source text of every UI kit component (not its tests). */
const kitSources = import.meta.glob<string>(
  ['../components/ui/*.tsx', '!../components/ui/*.test.tsx'],
  { query: '?raw', import: 'default', eager: true },
);

/** Every `#RRGGBB` or `rgba(r, g, b, a)` color in a theme fragment, as upper-case hex. */
function colorsIn(value: unknown): string[] {
  return strings(value).flatMap((s) => {
    const rgba = /^rgba\((\d+),\s*(\d+),\s*(\d+),/.exec(s);
    if (rgba) {
      const hex = rgba
        .slice(1, 4)
        .map((n) => Number(n).toString(16).padStart(2, '0'))
        .join('');
      return [`#${hex.toUpperCase()}`];
    }
    return /^#[0-9a-f]{6}$/i.test(s) ? [s.toUpperCase()] : [];
  });
}

function strings(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(strings);
  if (value && typeof value === 'object') return Object.values(value).flatMap(strings);
  return [];
}

describe('theme tokens', () => {
  it('body text stays readable on both surfaces and on primary buttons', () => {
    expect(contrast(colors.text, colors.surface)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(colors.text, colors.elevated)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(colors.textMuted, colors.elevated)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(colors.text, colors.primary)).toBeGreaterThanOrEqual(4.5);
  });

  it('every chart series color keeps 3:1 contrast on the card color', () => {
    for (const color of chartPalette) {
      expect(contrast(color, colors.elevated), color).toBeGreaterThanOrEqual(3);
    }
  });

  it('the ECharts theme only uses brand token colors', () => {
    const allowed = new Set<string>([...Object.values(colors), ...chartPalette]);
    const used = colorsIn(echartsTheme);
    expect(used.length).toBeGreaterThan(10);
    expect(used.filter((c) => !allowed.has(c))).toEqual([]);
  });

  it('every token the UI kit uses as a text color keeps 4.5:1 on cards and on the page', () => {
    const used = new Set<string>();
    for (const source of Object.values(kitSources)) {
      for (const match of source.matchAll(/(?<![\w-])text-([a-z]+(?:-[a-z]+)*)/g)) {
        const name = match[1] ?? '';
        if (TOKEN_BY_CLASS_NAME.has(name)) used.add(name);
      }
    }
    expect(Object.keys(kitSources).length).toBeGreaterThanOrEqual(11);
    expect(used).toContain('text-muted');
    for (const name of used) {
      const hex = TOKEN_BY_CLASS_NAME.get(name) ?? '';
      expect(contrast(hex, colors.elevated), `text-${name} on elevated`).toBeGreaterThanOrEqual(
        4.5,
      );
      expect(contrast(hex, colors.surface), `text-${name} on surface`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('starts the visualMap ramp at a color that differs from cards and the page', () => {
    const [low] = echartsTheme.visualMap.inRange.color;
    expect(low).not.toBe(colors.elevated);
    expect(low).not.toBe(colors.surface);
  });

  it('themes the dataZoom preview, handles and brush and every split area in brand colors', () => {
    const { dataZoom } = echartsTheme;
    const parts: Record<string, unknown> = {
      'dataZoom.dataBackground': dataZoom.dataBackground,
      'dataZoom.selectedDataBackground': dataZoom.selectedDataBackground,
      'dataZoom.moveHandleStyle': dataZoom.moveHandleStyle,
      'dataZoom.brushStyle': dataZoom.brushStyle,
      'dataZoom.emphasis.handleStyle': dataZoom.emphasis.handleStyle,
      'dataZoom.emphasis.moveHandleStyle': dataZoom.emphasis.moveHandleStyle,
      'categoryAxis.splitArea': echartsTheme.categoryAxis.splitArea,
      'valueAxis.splitArea': echartsTheme.valueAxis.splitArea,
      'timeAxis.splitArea': echartsTheme.timeAxis.splitArea,
      'logAxis.splitArea': echartsTheme.logAxis.splitArea,
    };
    for (const [name, part] of Object.entries(parts)) {
      expect(colorsIn(part).length, name).toBeGreaterThan(0);
    }
  });

  it('theme.css mirrors tokens.ts exactly (colors, radii and font)', () => {
    const vars = new Map(
      [...themeCss.matchAll(/--([a-z-]+):\s*([^;]+);/g)].map((m) => [m[1], (m[2] ?? '').trim()]),
    );
    const cssColors = Object.fromEntries(
      [...vars]
        .filter(([name]) => name?.startsWith('color-'))
        .map(([name, value]) => [name?.slice('color-'.length), value.toUpperCase()]),
    );
    expect(cssColors).toEqual(Object.fromEntries(TOKEN_BY_CLASS_NAME));
    expect(vars.get('radius-card')).toBe(`${radii.card}px`);
    expect(vars.get('radius-button')).toBe(`${radii.button}px`);
    expect(vars.get('radius-sheet')).toBe(`${radii.sheet}px`);
    expect(vars.get('font-sans')).toBe(fontFamily);
  });
});
