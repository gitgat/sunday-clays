import { useState, type ReactNode } from 'react';
import { Link, useParams } from 'react-router';
import { ApiError } from '../../../api/errors';
import { cx } from '../../../components/ui/cx';
import { EmptyState } from '../../../components/ui/EmptyState';
import { getDeviceId } from '../../../lib/device';
import { getMe, isMeSkipped } from '../../../lib/me';
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
 * Where each block sits. A phone stacks them in this order (the column wrappers are `contents`
 * below 1024 px, so every block is an item of one flex column); from 1024 px the main column
 * (lead, feed, More) sits beside the rail (you, next, pulse, details), each in this order.
 */
export const SHEET_ORDER = {
  masthead: 'order-1 lg:order-none lg:col-span-3',
  numbers: 'order-2 lg:order-none lg:col-span-3',
  you: 'order-3',
  lead: 'order-4',
  feed: 'order-5',
  more: 'order-6',
  next: 'order-7',
  pulse: 'order-8',
  details: 'order-9',
} as const;

function Block({ name, children }: { name: keyof typeof SHEET_ORDER; children: ReactNode }) {
  return (
    <div
      data-sheet-block={name}
      className={cx('flex min-w-0 flex-col gap-4 empty:hidden', SHEET_ORDER[name])}
    >
      {children}
    </div>
  );
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
  const { date, latest } = issue.masthead;
  const bumps = useBumps(date, deviceId);
  const shared = { issue, bumps: bumps.data, deviceId, meId, noteId: NOTE_ID };
  return (
    <div className="flex flex-col gap-4 lg:grid lg:grid-cols-3 lg:items-start">
      <Block name="masthead">
        <Masthead issue={issue} />
      </Block>
      <Block name="numbers">
        <Numbers issue={issue} />
      </Block>
      <div className="contents lg:col-span-2 lg:flex lg:min-w-0 lg:flex-col lg:gap-4">
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
      <div className="contents lg:flex lg:min-w-0 lg:flex-col lg:gap-4">
        <Block name="you">
          <YourSunday
            meId={meId}
            skipped={skipped}
            widgets={widgets}
            onPicked={setMeId}
            onCleared={() => setMeId(null)}
            onSkipped={() => setSkipped(true)}
          />
        </Block>
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
      </div>
    </div>
  );
}

function SheetError({ error }: { error: Error }) {
  if (error instanceof ApiError && error.status === 404) {
    return (
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
    );
  }
  return <EmptyState title="Couldn't load the Sunday Sheet" description="Try again in a moment." />;
}

/** The Sunday Sheet: `/sheet/:date` (and, once Home retires, `/` for the latest issue). */
export function SheetPage({ widgets = homeWidgets }: { widgets?: HomeWidget[] }) {
  const { date } = useParams();
  const sheet = useSheet(date ?? 'latest');
  const [deviceId] = useState<string | null>(getDeviceId);
  if (sheet.isPending) return <SheetSkeleton />;
  if (sheet.isError) return <SheetError error={sheet.error} />;
  return <SheetBody issue={sheet.data} deviceId={deviceId} widgets={widgets} />;
}
