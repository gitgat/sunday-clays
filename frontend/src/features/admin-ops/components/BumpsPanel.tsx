import { useEffect, useRef, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { Skeleton } from '../../../components/ui/Skeleton';
import { formatDay } from '../../home/format';
import { AdminError } from '../../admin/components/AdminError';
import { useBumpedPosts, useWipeBumps, type BumpedPost } from '../api';

function BumpedRow({ post }: { post: BumpedPost }) {
  const [confirming, setConfirming] = useState(false);
  const row = useRef<HTMLLIElement>(null);
  const moved = useRef(false);
  // Keyboard users follow the swap: confirming lands on "Keep them" (the safe choice), and
  // cancelling returns to "Wipe bumps". Skipped on first render so the list never grabs focus.
  useEffect(() => {
    if (!moved.current) return;
    row.current?.querySelector<HTMLButtonElement>('[data-focus-target]')?.focus();
  }, [confirming]);
  const toggle = (next: boolean) => {
    moved.current = true;
    setConfirming(next);
  };
  const wipe = useWipeBumps();
  const plural = post.bumps === 1 ? 'bump' : 'bumps';
  return (
    <li
      ref={row}
      className="flex flex-col gap-2 border-t border-outline-variant pt-3 first:border-t-0 first:pt-0"
    >
      <p className="break-words">{post.label}</p>
      <p className="text-sm text-text-muted">
        {`${String(post.bumps)} ${plural}`}
        {post.issue_date !== null && ` · ${formatDay(post.issue_date)}`}
        {!post.current && post.issue_date !== null && ' · no longer on a Sheet'}
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
          <Button variant="ghost" data-focus-target onClick={() => toggle(false)}>
            Keep them
          </Button>
        </div>
      ) : (
        <Button
          variant="tonal"
          className="self-start"
          aria-label={`Wipe bumps on ${post.label}`}
          data-focus-target
          onClick={() => toggle(true)}
        >
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
