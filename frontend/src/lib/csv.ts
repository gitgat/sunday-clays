import { downloadBlob } from './download';

export interface CsvColumn {
  key: string;
  label: string;
}

export type CsvRow = Record<string, string | number | null | undefined>;

/** Text cells starting with these could run as spreadsheet formulas; they get a leading quote. */
const FORMULA_START = /^[=+\-@\t\r]/;

function cell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '';
  let text = typeof value === 'number' ? (Number.isFinite(value) ? String(value) : '') : value;
  if (typeof value === 'string' && FORMULA_START.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** RFC 4180 CSV (CRLF line endings) with a header row of column labels. */
export function toCsv(columns: readonly CsvColumn[], rows: readonly CsvRow[]): string {
  const lines = [
    columns.map((c) => cell(c.label)).join(','),
    ...rows.map((row) => columns.map((c) => cell(row[c.key])).join(',')),
  ];
  return `${lines.join('\r\n')}\r\n`;
}

/** Downloads rows as `<name>.csv` (UTF-8 with BOM so Excel reads accents correctly). */
export function downloadCsv(
  name: string,
  columns: readonly CsvColumn[],
  rows: readonly CsvRow[],
): void {
  const filename = name.endsWith('.csv') ? name : `${name}.csv`;
  const blob = new Blob(['\uFEFF', toCsv(columns, rows)], { type: 'text/csv;charset=utf-8' });
  downloadBlob(blob, filename);
}
