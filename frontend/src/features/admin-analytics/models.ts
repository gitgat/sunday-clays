import type { EChartsOption } from 'echarts';
import { barOption } from '../../components/charts/builders/bar';
import type { TabularData } from '../../components/charts/types';
import type { BumpsSummary, PageKindViews, Uptake, Visitors } from './api';

export type Model = TabularData & { option: EChartsOption };
export type Per = 'day' | 'week';

/** Plain names for the page kinds; copy says "Sunday", never "event" (Global Constraints). */
const PAGE_KIND_LABELS = new Map<string, string>([
  ['home', 'Home'],
  ['profile', 'Shooter profiles'],
  ['event', 'One Sunday'],
  ['events-list', 'Sundays list'],
  ['leaderboards', 'Leaderboards'],
  ['records', 'Records'],
  ['club', 'Club'],
  ['stations', 'Stations'],
  ['weather', 'Weather'],
  ['yir', 'Year in Review'],
  ['explorer', 'Explorer'],
  ['achievements', 'Trophies'],
  ['race', 'Race'],
  ['compare', 'Compare'],
  ['admin', 'Admin pages'],
  ['other', 'Other pages'],
]);

/** A kind added later without a label shows as its own name. */
export function pageKindLabel(kind: string): string {
  return PAGE_KIND_LABELS.get(kind) ?? kind;
}

export function visitorsModel(data: Visitors, per: Per): Model {
  const columns: TabularData['columns'] = [
    per === 'day'
      ? { key: 'day', label: 'Day', type: 'date' }
      : { key: 'week', label: 'Week of', type: 'date' },
    { key: 'devices', label: 'Devices', type: 'int' },
  ];
  const rows =
    per === 'day'
      ? data.days.map((d) => ({ day: d.day, devices: d.devices }))
      : data.weeks.map((w) => ({ week: w.week, devices: w.devices }));
  return { columns, rows, option: barOption({ columns, rows }, { x: per, y: ['devices'] }) };
}

export function pageKindsModel(data: PageKindViews[]): Model {
  const columns: TabularData['columns'] = [
    { key: 'page', label: 'Page', type: 'string' },
    { key: 'views', label: 'Views', type: 'int' },
  ];
  const rows = data.map((k) => ({ page: pageKindLabel(k.page_kind), views: k.views }));
  const option = barOption(
    { columns, rows },
    { x: 'page', y: ['views'], horizontal: true, labels: true },
  );
  return { columns, rows, option };
}

export function bumpsModel(data: BumpsSummary): Model {
  const columns: TabularData['columns'] = [
    { key: 'day', label: 'Day', type: 'date' },
    { key: 'bumps', label: 'Bumps', type: 'int' },
  ];
  const rows = data.days.map((d) => ({ day: d.day, bumps: d.bumps }));
  return { columns, rows, option: barOption({ columns, rows }, { x: 'day', y: ['bumps'] }) };
}

export function uptakeModel(data: Uptake): Model {
  const columns: TabularData['columns'] = [
    { key: 'week', label: 'Week of', type: 'date' },
    { key: 'picked', label: 'Picked a name', type: 'int' },
    { key: 'skipped', label: 'Skipped', type: 'int' },
    { key: 'none', label: 'Not answered', type: 'int' },
  ];
  const rows = data.weeks.map((w) => ({
    week: w.week,
    picked: w.picked,
    skipped: w.skipped,
    none: w.none,
  }));
  const option = barOption(
    { columns, rows },
    { x: 'week', y: ['picked', 'skipped', 'none'], stack: true, yName: 'Devices' },
  );
  return { columns, rows, option };
}
