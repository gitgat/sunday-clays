import {
  useEffect,
  useRef,
  useState,
  type ElementType,
  type ReactNode,
  type RefObject,
} from 'react';
import { Link, useParams } from 'react-router';
import { ApiError } from '../../../api/errors';
import { cx } from '../../../components/ui/cx';
import { EmptyState } from '../../../components/ui/EmptyState';
import { getDeviceId } from '../../../lib/device';
import { getMe, isMeSkipped } from '../../../lib/me';
import { useMeta } from '../../../lib/timeWindow';
import { daysBack, EIGHT_WEEK_DAYS } from '../../../lib/timeWindowChoice';
import { ClubPulse } from '../../home/components/ClubPulse';
import { WidgetSlot } from '../../home/components/WidgetSlot';
import { homeWidgets, type HomeWidget } from '../../home/widgets';
import { useBumps, useSheet, type SheetIssue } from '../api';
import { Feed } from '../components/Feed';
import { Masthead } from '../components/Masthead';
import { MoreFromSunday } from '../components/MoreFromSunday';
import { Numbers } from '../components/Numbers';
import { SheetSkeleton } from '../components/SheetSkeleton';
import { SundayDetails } from '../components/SundayDetails';
import { YourSunday } from '../components/YourSunday';

const NOTE_ID = 'sheet-bumps-off';

/**
 * Where the grid items sit from 1024 px. The DOM is in phone order (masthead, numbers, Your
 * Sunday, then the main column, then the rail), so reading and focus order match what a phone
 * shows (WCAG 1.3.2, 2.4.3); the desktop grid places each piece explicitly instead of reordering.
 */
export const SHEET_PLACEMENT = {
  masthead: 'lg:col-span-3 lg:col-start-1 lg:row-start-1',
  numbers: 'lg:col-span-3 lg:col-start-1 lg:row-start-2',
  you: 'lg:col-start-3 lg:row-start-3',
  main: 'lg:col-span-2 lg:col-start-1 lg:row-span-2 lg:row-start-3',
  rail: 'lg:col-start-3 lg:row-start-4',
  /** With no Your Sunday above it, the rail takes the whole right column. */
  railAlone: 'lg:col-start-3 lg:row-span-2 lg:row-start-3',
} as const;

/** The h1 of the states that have no masthead (no issue yet, not found, error). */
function SheetTitle({ titleRef }: { titleRef?: RefObject<HTMLHeadingElement | null> }) {
  return (
    <h1 ref={titleRef} tabIndex={-1} className="text-3xl font-bold uppercase tracking-wide">
      The Sunday Sheet
    </h1>
  );
}

function Block({
  name,
  className,
  as: Tag = 'div',
  label,
  children,
}: {
  name: string;
  className?: string;
  /** `aside` makes the block a complementary landmark; give it a `label`. */
  as?: ElementType;
  label?: string;
  children: ReactNode;
}) {
  return (
    <Tag
      data-sheet-block={name}
      aria-label={label}
      className={cx('flex min-w-0 flex-col gap-4 empty:hidden', className)}
    >
      {children}
    </Tag>
  );
}

/** Moves focus to a heading inside `root` (a script-only target, like a linked Card). */
function focusHeading(root: HTMLElement | null) {
  const heading = root?.querySelector<HTMLElement>('h2, h3');
  if (heading === null || heading === undefined) return false;
  heading.tabIndex = -1;
  heading.focus();
  return true;
}

function SheetBody({
  issue,
  deviceId,
  widgets,
}: {
  issue: SheetIssue;
  deviceId: string | null;
  widgets: HomeWidget[];
}) {
  const [meId, setMeId] = useState<number | null>(getMe);
  const [skipped, setSkipped] = useState(isMeSkipped);
  const mainRef = useRef<HTMLDivElement>(null);
  const skippedBefore = useRef(skipped);
  const { date, latest } = issue.masthead;
  // "Not a shooter / skip" removes the card that held focus: carry on at the main column's first heading.
  useEffect(() => {
    if (skipped && !skippedBefore.current) focusHeading(mainRef.current);
    skippedBefore.current = skipped;
  }, [skipped]);
  const showYou = meId !== null || !skipped;
  const bumps = useBumps(date, deviceId);
  const shared = { issue, bumps: bumps.data, deviceId, meId, noteId: NOTE_ID };
  return (
    <div className="flex flex-col gap-4 lg:grid lg:grid-cols-3 lg:grid-rows-[auto_auto_auto_1fr] lg:items-start">
      <Block name="masthead" className={SHEET_PLACEMENT.masthead}>
        <Masthead issue={issue} />
      </Block>
      <Block name="numbers" className={SHEET_PLACEMENT.numbers}>
        <Numbers issue={issue} />
      </Block>
      {showYou && (
        <Block name="you" as="aside" label="Personal" className={SHEET_PLACEMENT.you}>
          <YourSunday
            meId={meId}
            skipped={skipped}
            widgets={widgets}
            onPicked={setMeId}
            onCleared={() => setMeId(null)}
            onSkipped={() => setSkipped(true)}
          />
        </Block>
      )}
      <div
        ref={mainRef}
        data-sheet-column="main"
        className={cx('flex min-w-0 flex-col gap-4', SHEET_PLACEMENT.main)}
      >
        <Block name="lead">
          <WidgetSlot slot="hero" widgets={widgets} meId={meId} issue={issue} />
        </Block>
        <Block name="feed">
          {bumps.isError && (
            <p className="text-sm text-text-muted">Bump counts aren't available right now</p>
          )}
          <Feed {...shared} />
        </Block>
        <Block name="more">
          <MoreFromSunday {...shared} />
        </Block>
      </div>
      <aside
        aria-label="More about this Sunday"
        data-sheet-column="rail"
        className={cx(
          'flex min-w-0 flex-col gap-4',
          showYou ? SHEET_PLACEMENT.rail : SHEET_PLACEMENT.railAlone,
        )}
      >
        {latest && (
          <Block name="next">
            <WidgetSlot slot="main" widgets={widgets} meId={meId} issue={issue} />
          </Block>
        )}
        <Block name="pulse">
          <ClubPulse range={{ from: daysBack(date, EIGHT_WEEK_DAYS - 1), to: date }} />
        </Block>
        <Block name="details">
          <SundayDetails date={date} latest={latest} />
        </Block>
      </aside>
    </div>
  );
}

/**
 * `/` on a fresh install: no Sunday has been held, so there is no issue to show. The rail's
 * personal and next-Sunday pieces need no issue, so they stay.
 */
function NoSheetYet({ widgets }: { widgets: HomeWidget[] }) {
  const [meId, setMeId] = useState<number | null>(getMe);
  const [skipped, setSkipped] = useState(isMeSkipped);
  const showYou = meId !== null || !skipped;
  const titleRef = useRef<HTMLHeadingElement>(null);
  const skippedBefore = useRef(skipped);
  // Skipping removes the card that held focus: carry on at the h1.
  useEffect(() => {
    if (skipped && !skippedBefore.current) titleRef.current?.focus();
    skippedBefore.current = skipped;
  }, [skipped]);
  const meta = useMeta();
  // With Sundays already scored (partly) the workbook is in; only full results are missing.
  const description = meta.isPending
    ? undefined
    : meta.data?.last_score_date
      ? 'No Sunday has full results yet.'
      : 'An admin can upload the scores workbook.';
  return (
    <div className="flex flex-col gap-4 lg:grid lg:grid-cols-3 lg:items-start">
      <div className="flex min-w-0 flex-col gap-4 lg:col-span-2">
        <SheetTitle titleRef={titleRef} />
        <EmptyState
          title="No Sunday Sheet yet"
          description={description}
          action={
            <Link to="/events" className="inline-flex min-h-11 items-center underline">
              All Sundays
            </Link>
          }
        />
      </div>
      <div className="flex min-w-0 flex-col gap-4">
        {showYou && (
          <aside aria-label="Personal" className="flex min-w-0 flex-col gap-4">
            <YourSunday
              meId={meId}
              skipped={skipped}
              widgets={widgets}
              onPicked={setMeId}
              onCleared={() => setMeId(null)}
              onSkipped={() => setSkipped(true)}
            />
          </aside>
        )}
        <WidgetSlot slot="main" widgets={widgets} meId={meId} />
      </div>
    </div>
  );
}

function SheetError({
  error,
  dated,
  widgets,
}: {
  error: Error;
  dated: boolean;
  widgets: HomeWidget[];
}) {
  // A date that is not a Sunday's (a typo like 2026-9-27) fails FastAPI's path check with 422.
  const gone =
    error instanceof ApiError &&
    (error.status === 404 || (dated && [400, 422].includes(error.status)));
  if (gone) {
    if (!dated) return <NoSheetYet widgets={widgets} />;
    return (
      <>
        <SheetTitle />
        <EmptyState
          title="No Sunday Sheet for this date"
          description="There is a Sheet for every Sunday with full results."
          action={
            <span className="flex flex-wrap justify-center gap-3">
              <Link to="/events" className="inline-flex min-h-11 items-center underline">
                All issues
              </Link>
              <Link to="/" className="inline-flex min-h-11 items-center underline">
                Latest issue
              </Link>
            </span>
          }
        />
      </>
    );
  }
  return (
    <>
      <SheetTitle />
      <EmptyState title="Couldn't load the Sunday Sheet" description="Try again in a moment." />
    </>
  );
}

/** The Sunday Sheet: `/` serves the latest issue and `/sheet/:date` any held Sunday's. */
export function SheetPage({ widgets = homeWidgets }: { widgets?: HomeWidget[] }) {
  const { date } = useParams();
  const sheet = useSheet(date ?? 'latest');
  const [deviceId] = useState<string | null>(getDeviceId);
  if (sheet.isPending) return <SheetSkeleton />;
  if (sheet.isError) {
    return <SheetError error={sheet.error} dated={date !== undefined} widgets={widgets} />;
  }
  return <SheetBody issue={sheet.data} deviceId={deviceId} widgets={widgets} />;
}
