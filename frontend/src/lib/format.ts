const DASH = '—';
const MINUS = '−';

type Maybe = number | null | undefined;

const isNum = (v: Maybe): v is number => typeof v === 'number' && Number.isFinite(v);

// Intl formatters are costly to build and tables format every cell: build one per options key.
const numberFormats = new Map<number, Intl.NumberFormat>();

function numberFormat(digits: number): Intl.NumberFormat {
  let format = numberFormats.get(digits);
  if (!format) {
    format = new Intl.NumberFormat('en-US', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
    numberFormats.set(digits, format);
  }
  return format;
}

export function formatNumber(v: Maybe, digits = 0): string {
  if (!isNum(v)) return DASH;
  return numberFormat(digits).format(v);
}

/** `v` is already a percentage (0–100). */
export function formatPercent(v: Maybe, digits = 1): string {
  return isNum(v) ? `${formatNumber(v, digits)}%` : DASH;
}

/** +1.5 / −1.5 (true minus sign) / 0.0 */
export function formatSigned(v: Maybe, digits = 1): string {
  if (!isNum(v)) return DASH;
  const magnitude = formatNumber(Math.abs(v), digits);
  if (Number(magnitude.replace(/,/g, '')) === 0) return magnitude;
  return `${v > 0 ? '+' : MINUS}${magnitude}`;
}

export function formatTemp(f: Maybe): string {
  return isNum(f) ? `${Math.round(f)}°F` : DASH;
}

export function formatWind(mph: Maybe): string {
  return isNum(mph) ? `${Math.round(mph)} mph` : DASH;
}

export function formatPrecip(inches: Maybe): string {
  return isNum(inches) ? `${inches.toFixed(2)} in` : DASH;
}

/** Stored in hPa, displayed in inHg (× 0.02953, 2 dp) — Global Constraints. */
export function formatPressure(hPa: Maybe): string {
  return isNum(hPa) ? `${(hPa * 0.02953).toFixed(2)} inHg` : DASH;
}

/** Parses YYYY-MM-DD as a local calendar date (never shifted by the UTC offset). */
export function parseIsoDate(iso: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return null;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return d.getMonth() === Number(m[2]) - 1 ? d : null;
}

// The three date styles are fixed, so each formatter is built once.
const DATE = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
const SHORT_DATE = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' });
const MONTH = new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' });

function formatWith(iso: string | null | undefined, format: Intl.DateTimeFormat): string {
  const d = iso ? parseIsoDate(iso) : null;
  return d ? format.format(d) : DASH;
}

/** 2026-09-13 → Sep 13, 2026 */
export function formatDate(iso: string | null | undefined): string {
  return formatWith(iso, DATE);
}

/** 2026-09-13 → Sep 13 */
export function formatShortDate(iso: string | null | undefined): string {
  return formatWith(iso, SHORT_DATE);
}

/** 2025-03 → Mar 2025 */
export function formatMonth(yearMonth: string | null | undefined): string {
  return formatWith(yearMonth ? `${yearMonth}-01` : null, MONTH);
}
