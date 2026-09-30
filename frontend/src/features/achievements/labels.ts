import type { components } from '../../api/schema';

export type Category = components['schemas']['Category'];

export const CATEGORY_LABELS: Record<Category, string> = {
  milestone: 'Milestones',
  scoring: 'Scoring',
  calendar: 'Calendar',
  conditions: 'Conditions',
  stations: 'Stations',
  competition: 'Competition',
};

export const CATEGORIES: readonly Category[] = [
  'milestone',
  'scoring',
  'calendar',
  'conditions',
  'stations',
  'competition',
];

export function trophyTitle(trophy: { name: string; label: string | null }): string {
  return trophy.label === null ? trophy.name : `${trophy.name} — ${trophy.label}`;
}

export function formatCount(value: number): string {
  return Math.round(value).toLocaleString('en-US');
}

export function formatPct(pct: number): string {
  return `${pct.toFixed(1)}%`;
}
