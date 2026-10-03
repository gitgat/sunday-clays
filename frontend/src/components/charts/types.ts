import type { QueryKey } from '@tanstack/react-query';
import type { EChartsOption } from 'echarts';
import type { GlossaryTermId } from '../../features/glossary/terms';

/** Column/row data every chart, table and CSV export consumes (C10). Never schema types. */
export type ColumnType = 'date' | 'number' | 'string' | 'int';

export interface TabularColumn {
  key: string;
  label: string;
  type: ColumnType;
}

export type Cell = string | number | null;

export type TabularRow = Record<string, Cell>;

export interface TabularData {
  columns: TabularColumn[];
  rows: TabularRow[];
}

/** Chart types a ChartCard can switch between. */
export type ChartType = 'bar' | 'line' | 'heatmap';

/** One time-machine frame (race + bump builders); pages map API frames onto this. */
export interface LeaderboardFrame {
  date: string;
  rows: { id: number | string; name: string; value: number; rank: number }[];
}

/**
 * Plain-language copy for a chart or stat (docs: .superpowers/sdd/explainers/STYLE.md): what it
 * shows, how to read it and exactly what is computed. Written for a shooter, not an analyst.
 */
export interface Explainer {
  /** "What this shows": one or two plain sentences. */
  what: string;
  /** "How to read it": short bullets; the part is left out when empty or missing. */
  read?: readonly string[];
  /** "How it's worked out": short bullets of the exact arithmetic. */
  computed: readonly string[];
  /**
   * Tags the chart with the data it covers: 'windowed' = the active `w` with its dates, 'all-time' =
   * every Sunday, 'lifetime' = a career total, 'year' = one calendar year at a time.
   */
  scope?: 'windowed' | 'all-time' | 'lifetime' | 'year';
  /** Plan 19 D13: glossary terms the copy uses; shown as "Words used here" links. */
  terms?: readonly GlossaryTermId[];
  /** Terms the text names on purpose without linking (the glossary lint skips them). */
  noTerms?: readonly GlossaryTermId[];
}

/** What fullscreen and the CSV show instead of the inline data. Every field is optional. */
export interface ChartFull {
  /** Fullscreen chart; default: the inline `option`. */
  option?: EChartsOption | undefined;
  /** Fullscreen table and CSV columns; default: the inline `columns`. */
  columns?: TabularColumn[] | undefined;
  /** Fullscreen table and CSV rows; default: the inline `rows`. */
  rows?: TabularRow[] | undefined;
  /** Fullscreen chart height in px (the sheet scrolls); default '70dvh'. */
  height?: number | undefined;
  /** One plain sentence shown in fullscreen above the chart, e.g. "Every Sunday since 2019". */
  note?: string | undefined;
  /** Scope tag shown in fullscreen; default: a 'windowed' explainer becomes 'all-time' when `window` or full data is set, else the explainer's own scope. */
  scope?: Explainer['scope'];
}

/** Full data fetched only when fullscreen opens or CSV is pressed (TanStack Query, cached by key). */
export interface ChartFullQuery {
  /** Must differ from any key the page itself uses for other data shapes, e.g. [..., 'chart-full']. */
  queryKey: QueryKey;
  queryFn: () => Promise<ChartFull>;
}
