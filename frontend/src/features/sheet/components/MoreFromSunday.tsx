import type { FeedProps } from './Feed';
import { PostList } from './PostList';

/** The Sunday's other posts, grouped by family, closed until asked for. Still bumpable. */
export function MoreFromSunday({ issue, bumps, deviceId, meId, noteId }: FeedProps) {
  const total = issue.more.reduce((n, group) => n + group.posts.length, 0);
  if (total === 0) return null;
  return (
    <details className="min-w-0 rounded-card bg-elevated p-4 text-text">
      <summary className="min-h-11 cursor-pointer py-2 text-base font-medium">
        {`More from this Sunday (${String(total)})`}
      </summary>
      <div className="flex flex-col gap-4 pt-2">
        {issue.more.map((group) => (
          <section key={group.family} aria-label={group.label} className="flex flex-col gap-2">
            <h3 className="text-sm text-text-muted">{group.label}</h3>
            <PostList
              date={issue.masthead.date}
              posts={group.posts}
              bumps={bumps}
              deviceId={deviceId}
              meId={meId}
              noteId={noteId}
            />
          </section>
        ))}
      </div>
    </details>
  );
}
