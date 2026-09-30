import type { Page } from '@playwright/test';

/** Helpers for the specs of pages that follow the header time window (`?w=`). */

export type Preset = '8w' | '12m' | 'ytd' | 'all';

/** Picks a preset in the header time window: the segmented control on desktop, the select on a phone. */
export async function chooseWindow(page: Page, preset: Preset): Promise<void> {
  const select = page.getByRole('combobox', { name: 'Time window' });
  if (await select.isVisible()) {
    await select.selectOption(preset);
    return;
  }
  const label = { '8w': '8W', '12m': '12M', ytd: 'YTD', all: 'All' }[preset];
  await page
    .getByRole('group', { name: 'Time window' })
    .getByRole('button', { name: label, exact: true })
    .click();
}

/** Aug 3, 2026 (the wording of lib/format.ts formatDate, from an ISO date). */
export function longDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

/** "Aug 3 – Sep 27" inside the latest Sunday's year, both years spelled out otherwise. */
export function datesText(start: string, end: string, latest: string): string {
  const year = latest.slice(0, 4);
  const short = (iso: string) => longDate(iso).replace(/, \d{4}$/, '');
  return start.slice(0, 4) === year && end.slice(0, 4) === year
    ? `${short(start)} – ${short(end)}`
    : `${longDate(start)} – ${longDate(end)}`;
}

/** anchor minus `months` calendar months (day clamped) plus one day: the start of a 3M or 6M window. */
export function monthsBack(anchor: string, months: number): string {
  const [y = 0, m = 1, d = 1] = anchor.split('-').map(Number);
  const index = y * 12 + (m - 1) - months;
  const year = Math.floor(index / 12);
  const month = index % 12;
  const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  return new Date(Date.UTC(year, month, Math.min(d, lastDay) + 1)).toISOString().slice(0, 10);
}

/** anchor minus `days` days, as YYYY-MM-DD. */
export function daysBack(anchor: string, days: number): string {
  const d = new Date(`${anchor}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}
