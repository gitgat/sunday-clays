/** ClaySmasher defaultBrand tokens (Global Constraints). theme.css mirrors these values. */
export const colors = {
  surface: '#1A4D2E',
  elevated: '#2D5F3F',
  primary: '#9E5530',
  primaryContainer: '#C76D3F',
  accent: '#E8A77A',
  text: '#FEFBF6',
  textMuted: '#D4E7DD',
  outline: '#D1E7DA',
  outlineVariant: '#4A7C59',
  error: '#FEE2E2',
  errorContainer: '#DC2626',
} as const;

export type ColorToken = keyof typeof colors;

/** Radii in px: card 12, button 20, sheet 16. */
export const radii = { card: 12, button: 20, sheet: 16 } as const;

export const fontFamily = "Roboto, system-ui, -apple-system, 'Segoe UI', sans-serif";

/** Chart series colors; each keeps >= 3:1 contrast on the elevated card color. */
export const chartPalette = [
  '#E8A77A',
  '#90CAF9',
  '#D1E7DA',
  '#F59E0B',
  '#CE93D8',
  '#80CBC4',
  '#FFF59D',
  '#F48FB1',
] as const;

/** Grid and split lines: outline at low opacity. */
export const gridLine = 'rgba(209, 231, 218, 0.14)';
