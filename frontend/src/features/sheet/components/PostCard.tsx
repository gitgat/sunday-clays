import { useId, useState } from 'react';
import { Link } from 'react-router';
import { ExplainerPanel, ExplainerToggle } from '../../../components/ui/Explainer';
import { useExplicitWindow } from '../../../lib/timeWindowChoice';
import { TrophyIcon } from '../../achievements/components/TrophyIcon';
import { chartHref } from '../../insights/chartLink';
import { InsightExplainer } from '../../insights/components/InsightExplainer';
import { isMine } from '../../insights/components/InsightList';
import { Segments } from '../../insights/segments';
import type { BumpState, SheetPost, SheetPostType } from '../api';
import { sheetExplainers } from '../explainers';
import { BumpButton } from './BumpButton';

export const TYPE_LABELS: Record<SheetPostType, string> = {
  milestone: 'Milestone',
  improvement: 'On the up',
  trophy: 'Trophy unlocked',
  conditions: 'The day',
  welcome: 'Welcome',
  on_this_day: 'On this day',
  other: 'From the Sunday',
};

/** The headline names this many holders (analytics/sheet.py NAMES_SHOWN); more get a list. */
export const HEADLINE_NAMES = 3;
/** The holder list shows this many names until "+N more" opens the rest in place. */
export const HOLDERS_SHOWN = 8;

const ACTION =
  'inline-flex min-h-11 items-center rounded-button px-3 text-sm text-accent hover:underline';

type Holder = NonNullable<SheetPost['trophy']>['holders'][number];

/** Everyone who earned the trophy, each linked; past HOLDERS_SHOWN the rest open in place. */
function TrophyHolders({ holders }: { holders: Holder[] }) {
  const [all, setAll] = useState(false);
  const listId = useId();
  const extra = holders.length - HOLDERS_SHOWN;
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <p className="text-sm text-text-muted">Earned by</p>
      <ul id={listId} aria-label="Earned by" className="flex flex-wrap gap-x-3">
        {holders.map((h, i) => (
          <li key={h.shooter_id} hidden={!all && i >= HOLDERS_SHOWN}>
            <Link
              to={`/shooters/${String(h.shooter_id)}`}
              className="inline-flex min-h-11 items-center underline underline-offset-2"
            >
              {h.name}
            </Link>
          </li>
        ))}
      </ul>
      {extra > 0 && (
        <button
          type="button"
          aria-expanded={all}
          aria-controls={listId}
          onClick={() => setAll((v) => !v)}
          className="min-h-11 self-start rounded-button px-3 text-sm text-text-muted hover:text-text"
        >
          {all ? 'Show fewer' : `+${String(extra)} more`}
        </button>
      )}
    </div>
  );
}

/** An insight post's extra charts (its `chart.also`), as Home's insight cards linked them. */
function AlsoLinks({ insight, you }: { insight: NonNullable<SheetPost['insight']>; you: boolean }) {
  const viewerWindow = useExplicitWindow();
  return insight.chart.also.map((extra, i) => {
    const text = you && extra.label_you ? extra.label_you : extra.label;
    return (
      <Link
        key={`${String(i)}-${extra.anchor ?? ''}`}
        to={chartHref(extra, viewerWindow)}
        aria-label={`See the chart: ${text}`}
        className={ACTION}
      >
        {text}
      </Link>
    );
  });
}

export interface PostCardProps {
  post: SheetPost;
  date: string;
  deviceId: string | null;
  bumps: BumpState | undefined;
  meId: number | null;
  /** The id of the note that says why bumps are off. */
  noteId: string;
}

/**
 * One post: its type, a "New" tag, its headline (names link to profiles), trophy art and everyone
 * who earned a trophy, the bump button, any extra charts and "How we worked it
 * out" (an insight's own explainer, or the "On this day" one). The viewer's own single-shooter
 * insight reads in the second person.
 */
export function PostCard({ post, date, deviceId, bumps, meId, noteId }: PostCardProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const insight = post.insight ?? null;
  const you = insight !== null && isMine(insight, meId);
  const headline = you && insight.headline_you !== null ? insight.headline_you : post.headline;
  const holders = post.trophy?.holders ?? [];
  const explained = insight !== null || post.on_this_day != null;
  return (
    <li
      data-post-key={post.post_key}
      data-post-type={post.type}
      className="flex min-w-0 flex-col gap-2 rounded-card bg-elevated p-4 text-text"
    >
      <p className="text-xs font-medium uppercase tracking-wide text-accent">
        {TYPE_LABELS[post.type]}
      </p>
      <div className="flex min-w-0 items-start gap-3">
        {post.trophy != null && (
          <TrophyIcon
            artKey={post.trophy.art_key}
            metal={post.trophy.metal}
            locked={false}
            size={48}
          />
        )}
        <p className="min-w-0 break-words text-base">
          {insight?.is_new === true && (
            <span className="mr-2 rounded-button bg-primary px-2 py-0.5 align-middle text-xs font-bold">
              New
            </span>
          )}
          <Segments segments={headline} />
        </p>
      </div>
      {holders.length > HEADLINE_NAMES && <TrophyHolders holders={holders} />}
      <div data-share-exclude="" className="flex flex-wrap items-center gap-2">
        <BumpButton
          date={date}
          postKey={post.post_key}
          deviceId={deviceId}
          state={bumps}
          noteId={noteId}
        />
        {insight !== null && <AlsoLinks insight={insight} you={you} />}
        {explained && (
          <ExplainerToggle
            label="How we worked it out"
            panelId={panelId}
            open={open}
            onToggle={() => setOpen((v) => !v)}
          />
        )}
      </div>
      {open &&
        (insight !== null ? (
          <InsightExplainer id={panelId} insight={insight} you={you} />
        ) : (
          <ExplainerPanel id={panelId} explainer={sheetExplainers.onThisDay} />
        ))}
    </li>
  );
}
