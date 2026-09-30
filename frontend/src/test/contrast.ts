import { colors } from '../theme/tokens';

/** WCAG 2 relative luminance of a `#RRGGBB` color. */
export function luminance(hex: string): number {
  const channel = (i: number) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

/** WCAG 2 contrast ratio between two `#RRGGBB` colors. */
export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

/** Scales every sRGB channel by `factor` (CSS `brightness()`, or `color-mix(in srgb, c p%, black)`). */
export function scale(hex: string, factor: number): string {
  const channel = (i: number) =>
    Math.min(255, Math.round(parseInt(hex.slice(i, i + 2), 16) * factor))
      .toString(16)
      .padStart(2, '0');
  return `#${channel(1)}${channel(3)}${channel(5)}`.toUpperCase();
}

const kebab = (name: string) => name.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);

/** Tailwind color name (`primary-container`) → token hex, for every brand token. */
export const TOKEN_BY_CLASS_NAME: ReadonlyMap<string, string> = new Map(
  Object.entries(colors).map(([name, hex]) => [kebab(name), hex]),
);

/** Hex of the `<prefix>-<token>` class in `className` (prefix e.g. `bg`, `hover:bg`, `border`). */
export function classColor(className: string, prefix: string): string {
  for (const cls of className.split(/\s+/)) {
    if (!cls.startsWith(`${prefix}-`)) continue;
    const hex = TOKEN_BY_CLASS_NAME.get(cls.slice(prefix.length + 1));
    if (hex !== undefined) return hex;
  }
  throw new Error(`no ${prefix}-<token> class in "${className}"`);
}
