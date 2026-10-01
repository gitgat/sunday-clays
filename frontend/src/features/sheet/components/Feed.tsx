import { EmptyState } from '../../../components/ui/EmptyState';
import type { BumpCounts, SheetIssue } from '../api';
import { PostList } from './PostList';

export const BUMPS_OFF = 'Bumps need this browser to remember you';

export interface FeedProps {
  issue: SheetIssue;
  bumps: BumpCounts | undefined;
  deviceId: string | null;
  meId: number | null;
  noteId: string;
}

/** The Sunday's posts in the server's order (best first, interleaved by type). */
export function Feed({ issue, bumps, deviceId, meId, noteId }: FeedProps) {
  const date = issue.masthead.date;
  return (
    <section aria-labelledby="sheet-feed" className="flex min-w-0 flex-col gap-3">
      <div>
        <h2 id="sheet-feed" className="text-lg font-medium">
          This Sunday
        </h2>
        <p className="text-sm text-text-muted">All round types · not affected by the filters</p>
      </div>
      {deviceId === null && (
        <p id={noteId} className="text-sm text-text-muted">
          {BUMPS_OFF}
        </p>
      )}
      {issue.posts.length === 0 ? (
        <EmptyState
          title="Nothing to report for this Sunday yet"
          description="Its stories appear here once the results are in."
        />
      ) : (
        <PostList
          date={date}
          posts={issue.posts}
          bumps={bumps}
          deviceId={deviceId}
          meId={meId}
          noteId={noteId}
          label="Posts"
        />
      )}
    </section>
  );
}
