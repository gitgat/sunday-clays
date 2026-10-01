import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { ApiError } from '../../../api/errors';
import { EmptyState } from '../../../components/ui/EmptyState';
import { getDeviceId } from '../../../lib/device';
import { getMe } from '../../../lib/me';
import { useBumps, useSheet, type SheetIssue } from '../api';
import { Feed } from '../components/Feed';
import { Masthead } from '../components/Masthead';
import { MoreFromSunday } from '../components/MoreFromSunday';
import { Numbers } from '../components/Numbers';
import { SheetSkeleton } from '../components/SheetSkeleton';

const NOTE_ID = 'sheet-bumps-off';

function SheetBody({ issue, deviceId }: { issue: SheetIssue; deviceId: string | null }) {
  const [meId] = useState<number | null>(getMe);
  const bumps = useBumps(issue.masthead.date, deviceId);
  const shared = { issue, bumps: bumps.data, deviceId, meId, noteId: NOTE_ID };
  return (
    <div className="flex flex-col gap-4">
      <Masthead issue={issue} />
      <Numbers issue={issue} />
      {bumps.isError && (
        <p className="text-sm text-text-muted">Bump counts aren't available right now</p>
      )}
      <Feed {...shared} />
      <MoreFromSunday {...shared} />
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
export function SheetPage() {
  const { date } = useParams();
  const sheet = useSheet(date ?? 'latest');
  const [deviceId] = useState<string | null>(getDeviceId);
  if (sheet.isPending) return <SheetSkeleton />;
  if (sheet.isError) return <SheetError error={sheet.error} />;
  return <SheetBody issue={sheet.data} deviceId={deviceId} />;
}
