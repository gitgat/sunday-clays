import { TrophyIcon } from '../../achievements/components/TrophyIcon';
import { formatDay } from '../../home/format';
import type { SheetPost } from '../api';

/**
 * The image a post is shared as: a masthead strip, the headline, and the trophy art or the chart
 * it links to. Theme tokens only; no external fonts or images (the CSP allows none).
 */
export function PostShareCard({ post, date }: { post: SheetPost; date: string }) {
  const why = post.see_why;
  return (
    <article className="flex w-[360px] flex-col gap-3 rounded-card bg-surface p-4 text-text">
      <p className="border-b-2 border-accent pb-2 text-xs font-bold uppercase tracking-widest">
        {`The Sunday Sheet · ${formatDay(date)}`}
      </p>
      <div className="flex items-start gap-3">
        {post.trophy != null && (
          <TrophyIcon
            artKey={post.trophy.art_key}
            metal={post.trophy.metal}
            locked={false}
            size={64}
          />
        )}
        <p className="text-lg font-medium">
          {post.headline.map((s, i) =>
            s.t === 'num' ? (
              <strong key={`${String(i)}-num`}>{s.v}</strong>
            ) : (
              <span key={`${String(i)}-${s.t}`}>{s.v}</span>
            ),
          )}
        </p>
      </div>
      {why.kind === 'chart' && <p className="text-sm text-text-muted">{`📈 ${why.label}`}</p>}
      <p className="text-xs text-text-muted">Sunday Clays</p>
    </article>
  );
}
