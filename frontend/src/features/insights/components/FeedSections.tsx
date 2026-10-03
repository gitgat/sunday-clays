import { useState } from 'react';
import { useSearchParams } from 'react-router';
import { isCustomWindow, useTimeWindow } from '../../../lib/timeWindow';
import type { PageKey } from '../../../components/layout/pageTop';
import { Card } from '../../../components/ui/Card';
import { Skeleton } from '../../../components/ui/Skeleton';
import { formatShortDate } from '../../../lib/format';
import { getMe } from '../../../lib/me';
import { formatDay } from '../../shooters/format';
import { useHomeFeed, usePageFeed, useShooterFeed, useSundayFeed, type InsightFeed } from '../api';
import { BumpsOffNote, BumpsProvider } from '../../bumps/BumpsProvider';
import { feedKeys } from '../feedKeys';
import { InsightCard } from './InsightCard';
import { InsightList, isMine } from './InsightList';
import { KudosStrip } from './KudosStrip';
import { MoreInsights } from './MoreInsights';
import { latestSubtitle, RecapCard } from './RecapCard';

function isEmpty(feed: InsightFeed): boolean {
  return (
    feed.pinned == null &&
    feed.hero == null &&
    feed.spotlight == null &&
    feed.conditions == null &&
    feed.top.length === 0 &&
    feed.kudos.length === 0 &&
    feed.more.length === 0
  );
}

/**
 * A shooter's insights, for every viewer (D11): the pinned digest line across the top, the top 3
 * in a row on desktop, and the rest. "That's me" viewing their own profile reads the
 * second-person wording.
 */
export function ProfileInsights({ shooterId }: { shooterId: number }) {
  const [all, setAll] = useState(false);
  const feed = useShooterFeed(shooterId, all);
  if (feed.data === undefined || isEmpty(feed.data)) return null;
  const f = feed.data;
  const you = getMe() === shooterId;
  const first = f.pinned == null ? f.top : [f.pinned, ...f.top];
  return (
    <Card
      title="Insights"
      subtitle={
        f.as_of == null
          ? undefined
          : `As of ${formatDay(f.as_of)} · not affected by the time filter`
      }
    >
      <BumpsProvider keys={feedKeys(f)}>
        <div className="flex min-w-0 flex-col gap-3">
          <InsightList
            items={first}
            you={you}
            label="Top insights"
            columns={3}
            wideFirst={f.pinned != null}
          />
          <MoreInsights
            items={f.more}
            total={f.n_more}
            you={you}
            onShowAll={() => setAll(true)}
            loadingAll={all && feed.isPlaceholderData}
          />
        </div>
      </BumpsProvider>
    </Card>
  );
}

/**
 * A Sunday's stories: the conditions card and the top 3 (roll-ups applied) in a row on desktop,
 * kudos and the rest. The viewer's own single-shooter cards read in the second person.
 */
export function SundayInsights({ date }: { date: string }) {
  const feed = useSundayFeed(date);
  if (feed.data === undefined || isEmpty(feed.data)) return null;
  const f = feed.data;
  const meId = getMe();
  const first = f.conditions == null ? f.top : [f.conditions, ...f.top];
  return (
    <Card title="Insights" subtitle={`${formatDay(date)} · not affected by the time filter`}>
      <BumpsProvider keys={feedKeys(f)}>
        <div className="flex min-w-0 flex-col gap-3">
          <InsightList items={first} meId={meId} label="Top insights" columns={4} />
          <KudosStrip kudos={f.kudos} meId={meId} />
          <MoreInsights items={f.more} total={f.n_more} meId={meId} />
        </div>
      </BumpsProvider>
    </Card>
  );
}

/**
 * Stands in for the home cards while the feed loads, at roughly their final height, so the page
 * below does not jump when they arrive. One status for the lot; the extra cards are hidden from
 * assistive tech.
 */
function HomeInsightsPlaceholder() {
  return (
    <>
      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
        <Card>
          <Skeleton label="Loading insights" lines={4} className="min-h-40" />
        </Card>
        <Card>
          <div aria-hidden="true">
            <Skeleton label="Loading top story" lines={4} className="min-h-40" />
          </div>
        </Card>
      </div>
      <Card>
        <div aria-hidden="true">
          <Skeleton label="Loading more insights" lines={8} className="min-h-72" />
        </div>
      </Card>
    </>
  );
}

/**
 * Home: the pinned recap and the hero side by side on desktop, then "Shooter to know", the
 * latest Sunday's kudos across the page, one card per slot in a 2 × 2 grid, and the rest.
 */
export function HomeInsights({ meId }: { meId: number | null }) {
  const feed = useHomeFeed();
  if (feed.isPending) return <HomeInsightsPlaceholder />;
  // A failed fetch shows nothing: the other home cards already report an outage.
  if (feed.data === undefined || isEmpty(feed.data)) return null;
  const f = feed.data;
  const hasInsights =
    f.spotlight != null || f.top.length > 0 || f.kudos.length > 0 || f.more.length > 0;
  // "Bumps need this browser to remember you" goes inside a card, once: the Insights card, else the
  // Top story card, else the recap's card. Never a bare line between widgets.
  const noteHome = hasInsights ? 'insights' : f.hero != null ? 'hero' : 'recap';
  return (
    <BumpsProvider keys={feedKeys(f)} note={false}>
      {(f.pinned != null || f.hero != null) && (
        <div className="grid min-w-0 gap-4 lg:grid-cols-2">
          {f.pinned != null && <RecapCard insight={f.pinned} withNote={noteHome === 'recap'} />}
          {f.hero != null && (
            <Card title="Top story" subtitle={latestSubtitle(f.hero.anchor_date)}>
              {noteHome === 'hero' && <BumpsOffNote />}
              <ul aria-label="Top story" className="flex flex-col gap-3">
                <InsightCard insight={f.hero} you={isMine(f.hero, meId)} />
              </ul>
            </Card>
          )}
        </div>
      )}
      {hasInsights && (
        <Card
          tour="insights"
          title="Insights"
          subtitle={
            f.as_of == null
              ? 'Not affected by the time filter'
              : `As of ${formatDay(f.as_of)} · not affected by the time filter`
          }
        >
          <div className="flex min-w-0 flex-col gap-3">
            {noteHome === 'insights' && <BumpsOffNote />}
            {f.spotlight != null && (
              <section aria-label="Shooter to know" className="flex flex-col gap-2">
                <h3 className="text-sm font-medium text-text-muted">Shooter to know</h3>
                <ul className="flex flex-col gap-3">
                  <InsightCard insight={f.spotlight} you={isMine(f.spotlight, meId)} />
                </ul>
              </section>
            )}
            <KudosStrip
              kudos={f.kudos}
              meId={meId}
              title={f.as_of == null ? 'Kudos' : `Kudos from ${formatShortDate(f.as_of)}`}
            />
            <InsightList items={f.top} meId={meId} label="Around the club" columns={2} />
            <MoreInsights items={f.more} total={f.n_more} meId={meId} />
          </div>
        </Card>
      )}
    </BumpsProvider>
  );
}

/**
 * Club, leaderboards, records and stations: the page's top 3 (one per family) and the rest,
 * under the page title. Built as of the latest Sunday, so the header window does not change them.
 * The leaderboards feed is for the calendar year of the points race the board's "as of" date is
 * in (a Custom window has no "as of", like the board itself).
 */
export function PageInsights({ page }: { page: PageKey }) {
  const [search] = useSearchParams();
  const { window: timeWindow } = useTimeWindow();
  const asOf = page === 'leaderboards' && !isCustomWindow(timeWindow) ? search.get('as_of') : null;
  const season = asOf !== null && /^\d{4}-/.test(asOf) ? Number(asOf.slice(0, 4)) : null;
  const feed = usePageFeed(page, season);
  if (feed.data === undefined || isEmpty(feed.data)) return null;
  const f = feed.data;
  return (
    <Card
      title="Insights"
      subtitle={
        f.as_of == null
          ? undefined
          : `As of ${formatDay(f.as_of)} · not affected by the time filter`
      }
    >
      <BumpsProvider keys={feedKeys(f)}>
        <div className="flex min-w-0 flex-col gap-3">
          <InsightList items={f.top} meId={getMe()} label="Top insights" columns={3} />
          <MoreInsights items={f.more} total={f.n_more} meId={getMe()} />
        </div>
      </BumpsProvider>
    </Card>
  );
}
