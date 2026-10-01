import { useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { Skeleton } from '../../../components/ui/Skeleton';
import { formatDay } from '../../home/format';
import { AdminError } from '../../admin/components/AdminError';
import { useBumpedPosts, useWipeBumps, type BumpedPost } from '../api';

function BumpedRow({ post }: { post: BumpedPost }) {
  const [confirming, setConfirming] = useState(false);
  const wipe = useWipeBumps();
  const plural = post.bumps === 1 ? 'bump' : 'bumps';
  return (
    <li className="flex flex-col gap-2 border-t border-outline-variant pt-3 first:border-t-0 first:pt-0">
      <p className="break-words">{post.label}</p>
      <p className="text-sm text-text-muted">
        {`${String(post.bumps)} ${plural}`}
        {post.issue_date !== null && ` · ${formatDay(post.issue_date)}`}
        {!post.current && ' · no longer on a Sheet'}
      </p>
      <p className="break-all font-mono text-xs text-text-muted">{post.post_key}</p>
      {confirming ? (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="danger"
            loading={wipe.isPending}
            onClick={() => wipe.mutate(post.post_key)}
          >
            {`Yes, wipe ${String(post.bumps)} ${plural}`}
          </Button>
          <Button variant="ghost" onClick={() => setConfirming(false)}>
            Keep them
          </Button>
        </div>
      ) : (
        <Button variant="tonal" className="self-start" onClick={() => setConfirming(true)}>
          Wipe bumps
        </Button>
      )}
      {wipe.isError && <AdminError error={wipe.error} />}
    </li>
  );
}

/** Admin (Plan 14): every bumped post, with a two-step wipe that the audit log records. */
export function BumpsPanel() {
  const posts = useBumpedPosts();
  if (posts.isPending) return <Skeleton label="Loading bumped posts" />;
  if (posts.isError) return <AdminError error={posts.error} />;
  if (posts.data.length === 0) return <p className="text-text-muted">No bumps yet.</p>;
  return (
    <ul aria-label="Bumped posts" className="flex flex-col gap-3">
      {posts.data.map((post) => (
        <BumpedRow key={post.post_key} post={post} />
      ))}
    </ul>
  );
}
