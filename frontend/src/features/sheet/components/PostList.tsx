import type { SheetPost } from '../api';
import type { FeedProps } from './Feed';
import { PostCard } from './PostCard';

type PostListProps = Omit<FeedProps, 'issue'> & {
  date: string;
  posts: SheetPost[];
  label?: string;
};

/** A list of post cards with the issue's bumps, device and viewer wired in; Feed and More share it. */
export function PostList({ date, posts, bumps, deviceId, meId, noteId, label }: PostListProps) {
  return (
    <ol aria-label={label} className="flex flex-col gap-3">
      {posts.map((post) => (
        <PostCard
          key={post.post_key}
          post={post}
          date={date}
          deviceId={deviceId}
          bumps={bumps?.[post.post_key]}
          meId={meId}
          noteId={noteId}
        />
      ))}
    </ol>
  );
}
