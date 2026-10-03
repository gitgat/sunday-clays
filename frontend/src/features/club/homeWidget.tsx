import { Link } from 'react-router';
import { AboutBlock } from '../../components/ui/AboutBlock';
import { AdminPreviewBadge } from '../../components/ui/AdminPreviewBadge';
import { Card } from '../../components/ui/Card';
import { useFeature } from '../../lib/features';
import { formatDay } from '../home/format';
import type { HomeWidget } from '../home/widgets';
import { useClubMilestones } from './api';
import { explainers } from './explainers';
import { nextUp } from './milestones';

function ClubMilestoneCard() {
  const { visible } = useFeature('club_milestones');
  const query = useClubMilestones(visible);
  const { data } = query;
  if (!visible || !data?.latest) return null;
  const { latest } = data;
  const upcoming = nextUp(data.next);
  return (
    <Card
      title={
        <span className="inline-flex flex-wrap items-center gap-2">
          Club milestone
          <AdminPreviewBadge feature="club_milestones" />
        </span>
      }
    >
      <div className="flex flex-col gap-2">
        <p className="text-2xl font-medium">{latest.label}</p>
        <p className="text-sm text-text-muted">{`Passed on Sunday, ${formatDay(latest.event_date)}`}</p>
        {upcoming !== null && (
          <p>{`Next up: ${upcoming.label}, ${upcoming.remaining.toLocaleString('en-US')} to go`}</p>
        )}
        <Link
          to="/club#milestones"
          className="inline-flex min-h-11 items-center self-start underline"
        >
          All club milestones
        </Link>
        <AboutBlock explainer={explainers['club-milestone']} label="About club milestones" />
      </div>
    </Card>
  );
}

export const homeWidget: HomeWidget = {
  id: 'club-milestone',
  order: 20,
  slot: 'main',
  Component: ClubMilestoneCard,
};
