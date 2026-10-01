import { useState } from 'react';
import { useSearchParams } from 'react-router';
import { isCustomWindow, useTimeWindow } from '../../../lib/timeWindow';
import type { PageKey } from '../../../components/layout/pageTop';
import { Card } from '../../../components/ui/Card';
import { getMe } from '../../../lib/me';
import { formatDay } from '../../shooters/format';
import { usePageFeed, useShooterFeed, useSundayFeed, type InsightFeed } from '../api';
import { InsightList } from './InsightList';
import { KudosStrip } from './KudosStrip';
import { MoreInsights } from './MoreInsights';

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
      <div className="flex min-w-0 flex-col gap-3">
        <InsightList items={first} meId={meId} label="Top insights" columns={4} />
        <KudosStrip kudos={f.kudos} meId={meId} />
        <MoreInsights items={f.more} total={f.n_more} meId={meId} />
      </div>
    </Card>
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
      <div className="flex min-w-0 flex-col gap-3">
        <InsightList items={f.top} meId={getMe()} label="Top insights" columns={3} />
        <MoreInsights items={f.more} total={f.n_more} meId={getMe()} />
      </div>
    </Card>
  );
}
