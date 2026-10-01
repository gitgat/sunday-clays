import { skipToken, useQuery, useQueryClient } from '@tanstack/react-query';
import type { EChartsOption } from 'echarts';
import { Download, Maximize2, Table2 } from 'lucide-react';
import { useId, useMemo, useState, type ReactNode } from 'react';
import { downloadCsv } from '../../lib/csv';
import { formatDate } from '../../lib/format';
import {
  filterRowsByWindow,
  useWindowChoice,
  zoomToWindow,
  type WindowRange,
} from '../../lib/timeWindowChoice';
import { windowPhrase } from '../../lib/windowText';
import { useIsDesktop, useIsTouch } from '../../lib/useMediaQuery';
import { enumCodec, listCodec, useUrlState } from '../../lib/useUrlState';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { EmptyState } from '../ui/EmptyState';
import { WidenWindowButtons } from '../WidenWindowButtons';
import { applyTarget, markedCount, useChartTarget, useScrollToTarget } from './chartTarget';
import { ExplainerPanel, ExplainerToggle, ScopeTag } from '../ui/Explainer';
import { Sheet } from '../ui/Sheet';
import { DataTable } from './DataTable';
import { EChart, type EChartEvents } from './EChart';
import type { ChartFull, ChartFullQuery, Explainer, TabularData, TabularRow } from './types';
import { defaultZoom, withZoom, type ZoomMode } from './zoom';

export interface ChartFrameProps {
  title: string;
  /**
   * Under the title. A card whose explainer has `scope: 'windowed'` never puts the window or its
   * dates here: the scope tag beside "About this chart" already carries them.
   */
  subtitle?: string | undefined;
  option: EChartsOption;
  columns: TabularData['columns'];
  rows: TabularData['rows'];
  csvName: string;
  ariaLabel: string;
  /** Query-string key holding this frame's view state ("table", "full"). */
  urlKey: string;
  /** Default (defaultZoom): 'x' with x and y axes, 'y' for horizontal bars, 'none' otherwise. */
  zoom?: ZoomMode | undefined;
  /** A click handler that navigates passes its href through useRoundTypeHref (keeps `rt`). */
  onEvents?: EChartEvents | undefined;
  actions?: ReactNode;
  /** Rendered between the header and the chart (e.g. ChartCard's chips). */
  controls?: ReactNode;
  /** Chart height in px (default 320). */
  height?: number | undefined;
  /**
   * Drill-down link for each table row, on one cell per row: the `rowHrefKey` column's, else the
   * first text column's, else the first cell. The global `rt` filter is added.
   */
  rowHref?: ((row: TabularRow) => string) | undefined;
  /** The column whose cell carries `rowHref`; no cell is linked when no column has this key. */
  rowHrefKey?: string | undefined;
  /** Plain-language "About this chart" copy and the scope tag; also shown in fullscreen. */
  explainer?: Explainer | undefined;
  /**
   * Maps an insight link's `hl` keys to the chart's category labels (Plan 12 chart targets), e.g.
   * `shooterLabels('display_name')` for `s:{id}` keys. Default: the keys are labels or dates.
   */
  hlLabels?: ((keys: readonly string[], rows: readonly TabularRow[]) => string[]) | undefined;
  /**
   * The time window of the inline card. The inline chart opens zoomed to it and its Table lists
   * only the rows inside it (by the first date column, or `windowKey`); a window with no rows says
   * so, with 12M and "Show all time" buttons, instead of drawing all-time data under a window tag.
   * Fullscreen and the CSV never apply it: they open on the whole axis and every row. An insight
   * target's own window wins, inline and in fullscreen.
   */
  window?: WindowRange | null | undefined;
  /** The date column (YYYY-MM-DD) `window` trims the Table by; default: the first `date` column. */
  windowKey?: string | undefined;
  /** What the trimmed-table note calls the window; default "the time window" (the Sheet: "these 8 weeks"). */
  windowName?: string | undefined;
  /**
   * Wording for an empty window: "No rounds in the last 8 weeks. Last shot Aug 2, 2026." With
   * `fixed`, the window is the page's own (the Sheet's 8 weeks): it is named by `windowName` and
   * offers no widen buttons.
   */
  emptyWindow?: { none: string; last: string; fixed?: boolean } | undefined;
  /** Static full data for fullscreen and the CSV, when it is already loaded. */
  full?: ChartFull | undefined;
  /**
   * Full data fetched when fullscreen opens or CSV is pressed (cached by key). Fetched fields win
   * over `full` field by field.
   */
  fullQuery?: ChartFullQuery | undefined;
  /**
   * Whether the chart offers fullscreen (default true). False hides the Fullscreen control, for a
   * chart that has nothing more to show there.
   */
  fullscreen?: boolean | undefined;
}

const FULL_DATE = /^\d{4}-\d{2}-\d{2}/;
const NO_ROWS_WORDS = { none: 'No Sundays', last: 'Latest Sunday' };

type ViewFlag = 'table' | 'full';
const viewCodec = listCodec(enumCodec<ViewFlag>(['table', 'full']));
const NO_FLAGS: ViewFlag[] = [];

/** Every data chart renders inside this (C10): chart, Table toggle, CSV export, fullscreen. */
export function ChartFrame({
  title,
  subtitle,
  option,
  columns,
  rows,
  csvName,
  ariaLabel,
  urlKey,
  zoom,
  onEvents,
  actions,
  controls,
  height = 320,
  rowHref,
  rowHrefKey,
  explainer,
  hlLabels,
  window: initialWindow,
  windowKey,
  windowName = 'the time window',
  emptyWindow = NO_ROWS_WORDS,
  full,
  fullQuery,
  fullscreen: canFullscreen = true,
}: ChartFrameProps) {
  const [flags, setFlags] = useUrlState(urlKey, viewCodec, NO_FLAGS);
  const isDesktop = useIsDesktop();
  const isTouch = useIsTouch();
  const showTable = flags.includes('table');
  const fullscreen = canFullscreen && flags.includes('full');
  const toggle = (flag: ViewFlag) =>
    setFlags(flags.includes(flag) ? flags.filter((f) => f !== flag) : [...flags, flag]);
  const [aboutOpen, setAboutOpen] = useState(false);
  const panelId = useId();
  const { target, clear } = useChartTarget(urlKey);
  useScrollToTarget(urlKey, true);
  const queryClient = useQueryClient();
  const fetched = useQuery({
    queryKey: fullQuery?.queryKey ?? ['chart-full', urlKey],
    queryFn: fullQuery !== undefined && fullscreen ? fullQuery.queryFn : skipToken,
  });
  const fetchedData = fetched.data;
  // Static full data, with the fetched fields over it once they are in.
  const resolved = useMemo<ChartFull>(() => ({ ...full, ...fetchedData }), [full, fetchedData]);
  const fullColumns = resolved.columns ?? columns;
  const fullRows = resolved.rows ?? rows;
  const fullOption = resolved.option ?? option;

  // The inline Table lists the rows of the range the chart shows (an insight link's dates win over
  // the window), so Table and chart agree. It lists only that range's rows (the tag says so); fullscreen and the CSV list
  // every row. Trimmed only when every row carries a full date to compare.
  const [choice] = useWindowChoice();
  const dateKey = windowKey ?? columns.find((c) => c.type === 'date')?.key;
  const trimBy = useMemo(
    () =>
      initialWindow != null &&
      dateKey !== undefined &&
      rows.every((r) => FULL_DATE.test(String(r[dateKey] ?? '')))
        ? { key: dateKey, range: target.window ?? initialWindow }
        : null,
    [initialWindow, dateKey, rows, target.window],
  );
  const inlineRows = useMemo(
    () => (trimBy === null ? rows : filterRowsByWindow(rows, trimBy.key, trimBy.range)),
    [rows, trimBy],
  );
  const lastRow = useMemo(
    () =>
      trimBy === null
        ? null
        : (rows
            .map((r) => String(r[trimBy.key]).slice(0, 10))
            .filter((d) => d <= trimBy.range.to)
            .sort()
            .at(-1) ?? null),
    [rows, trimBy],
  );

  // An insight link's highlight, reference line and dates, over the page's own view. The inline
  // chart starts on `window`; fullscreen shows the whole axis unless the insight names dates.
  const targeted = useMemo(() => {
    const labels = hlLabels === undefined ? target.hl : hlLabels(target.hl, rows);
    const range = target.window ?? initialWindow ?? null;
    return applyTarget(range === null ? option : zoomToWindow(option, range), labels, target.ref);
  }, [option, rows, hlLabels, target, initialWindow]);
  const fullTargeted = useMemo(() => {
    const labels = hlLabels === undefined ? target.hl : hlLabels(target.hl, fullRows);
    const zoomed = target.window === null ? fullOption : zoomToWindow(fullOption, target.window);
    return applyTarget(zoomed, labels, target.ref);
  }, [fullOption, fullRows, hlLabels, target]);
  const mode = zoom ?? defaultZoom(option);
  const fullMode = zoom ?? defaultZoom(fullOption);
  // Stable option objects: this frame re-renders on every URL change (useUrlState).
  const inlineOption = useMemo(() => withZoom(targeted, mode, isTouch), [targeted, mode, isTouch]);
  const fullscreenOption = useMemo(
    () => withZoom(fullTargeted, fullMode, false),
    [fullTargeted, fullMode],
  );

  const [csvBusy, setCsvBusy] = useState(false);
  const [csvFailed, setCsvFailed] = useState(false);
  const downloadAll = async () => {
    if (fullQuery === undefined) {
      downloadCsv(csvName, fullColumns, fullRows);
      return;
    }
    setCsvBusy(true);
    try {
      // ensureQueryData: a result already cached (fullscreen was opened) is not fetched again.
      const data = { ...full, ...(await queryClient.ensureQueryData(fullQuery)) };
      downloadCsv(csvName, data.columns ?? columns, data.rows ?? rows);
      setCsvFailed(false);
    } catch {
      setCsvFailed(true);
    } finally {
      setCsvBusy(false);
    }
  };

  // The disclosure sits in the card (its header row would squeeze the title on a phone). Fullscreen
  // shows it inside the dialog instead: only one copy is on screen at a time.
  const about = (scope: Explainer['scope']) =>
    explainer === undefined ? null : (
      <>
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <ExplainerToggle
            label="About this chart"
            panelId={panelId}
            open={aboutOpen}
            onToggle={() => setAboutOpen((v) => !v)}
          />
          <ScopeTag scope={scope} />
        </div>
        {aboutOpen && <ExplainerPanel id={panelId} explainer={explainer} />}
      </>
    );

  const hasFull = initialWindow != null || full !== undefined || fullQuery !== undefined;
  const fullScope =
    resolved.scope ?? (explainer?.scope === 'windowed' && hasFull ? 'all-time' : explainer?.scope);

  // An insight link's own dates win over the window: only the page's own window can come up empty.
  const emptyInWindow = trimBy !== null && inlineRows.length === 0 && target.window === null;
  const emptyMessage = emptyInWindow && (
    <EmptyState
      title={`${emptyWindow.none} in ${
        emptyWindow.fixed === true ? windowName : windowPhrase(choice, initialWindow ?? null)
      }.`}
      description={lastRow === null ? undefined : `${emptyWindow.last} ${formatDate(lastRow)}.`}
      action={emptyWindow.fixed === true ? undefined : <WidenWindowButtons />}
    />
  );
  const trimmedNote = trimBy !== null && inlineRows.length < rows.length;

  const body = (inFullscreen: boolean) =>
    !inFullscreen && emptyMessage ? (
      emptyMessage
    ) : showTable ? (
      <>
        <DataTable
          caption={title}
          columns={inFullscreen ? fullColumns : columns}
          rows={inFullscreen ? fullRows : inlineRows}
          rowHref={rowHref}
          rowHrefKey={rowHrefKey}
        />
        {!inFullscreen && trimmedNote && (
          <p className="mt-2 min-w-0 text-xs text-text-muted">
            Showing {windowName}. Open fullscreen or download CSV for every Sunday.
          </p>
        )}
      </>
    ) : (
      <EChart
        option={inFullscreen ? fullscreenOption : inlineOption}
        height={inFullscreen ? (resolved.height ?? '70dvh') : height}
        ariaLabel={ariaLabel}
        onEvents={onEvents}
      />
    );

  // The same export from the card and from inside the fullscreen sheet.
  const csvButton = (
    <Button
      variant="ghost"
      aria-label="CSV"
      title="Download CSV"
      icon={<Download aria-hidden="true" className="size-4" />}
      loading={csvBusy}
      onClick={() => void downloadAll()}
    />
  );
  const csvAlert = csvFailed && (
    <p role="alert" className="mb-2 min-w-0 text-sm text-text">
      Couldn't download every row. Try again.
    </p>
  );

  const toolbar = (
    <>
      {actions}
      <Button
        variant="ghost"
        aria-pressed={showTable}
        aria-label="Table"
        title="Show the data as a table"
        icon={<Table2 aria-hidden="true" className="size-4" />}
        onClick={() => toggle('table')}
      />
      {csvButton}
      {canFullscreen && (
        <Button
          variant="ghost"
          aria-label="Fullscreen"
          aria-pressed={fullscreen}
          icon={<Maximize2 aria-hidden="true" className="size-4" />}
          onClick={() => toggle('full')}
        />
      )}
    </>
  );

  return (
    <Card id={`chart-${urlKey}`} title={title} subtitle={subtitle} actions={toolbar}>
      {!fullscreen && about(explainer?.scope)}
      {target.active && (
        <div
          className="mb-2 flex flex-wrap items-center gap-2 text-sm text-text-muted"
          data-marked={markedCount(targeted)}
        >
          <span>Showing what the insight points to.</span>
          <Button variant="ghost" onClick={clear}>
            Show the whole chart
          </Button>
        </div>
      )}
      {!fullscreen && csvAlert}
      {controls !== undefined && <div className="mb-3 flex flex-wrap gap-2">{controls}</div>}
      {fullscreen ? <div style={{ height }} aria-hidden="true" /> : body(false)}
      <Sheet
        open={fullscreen}
        onClose={() => toggle('full')}
        title={title}
        placement={isDesktop ? 'center' : 'bottom'}
        size="full"
      >
        {about(fullScope)}
        <div className="mb-2 flex justify-end">{csvButton}</div>
        {csvAlert}
        {fullQuery !== undefined && fetched.isPending && (
          <p role="status" className="mb-2 min-w-0 text-sm text-text-muted">
            Loading every row…
          </p>
        )}
        {fullQuery !== undefined && fetched.isError && (
          <div role="alert" className="mb-2 flex min-w-0 flex-wrap items-center gap-2 text-sm">
            <span className="min-w-0">
              Couldn't load the full data. Showing the chart as it is on the page.
            </span>
            <Button variant="ghost" onClick={() => void fetched.refetch()}>
              Try again
            </Button>
          </div>
        )}
        {resolved.note !== undefined && (
          <p className="mb-2 min-w-0 text-sm text-text-muted">{resolved.note}</p>
        )}
        {body(true)}
      </Sheet>
    </Card>
  );
}
