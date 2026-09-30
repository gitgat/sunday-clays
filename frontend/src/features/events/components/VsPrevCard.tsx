import { Link } from 'react-router';
import { Card } from '../../../components/ui/Card';
import { Stat } from '../../../components/ui/Stat';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import type { VsPrev } from '../api';
import { eventExplainers } from '../explainers';
import { formatDay, formatSigned } from '../format';
import { About } from './About';

export function VsPrevCard({ vsPrev }: { vsPrev: VsPrev | null }) {
  const href = useRoundTypeHref();
  return (
    <Card title="vs previous Sunday">
      {vsPrev === null ? (
        <p className="text-text-muted">First Sunday on record — nothing to compare.</p>
      ) : (
        <div className="flex flex-col gap-3">
          <About explainer={eventExplainers.vsPrev} label="About this comparison" />
          <p className="text-sm text-text-muted">
            Compared with the previous Sunday with full results,{' '}
            <Link
              to={href(`/events/${vsPrev.prev_date}`)}
              className="inline-flex min-h-11 min-w-11 items-center text-text underline underline-offset-2"
            >
              {formatDay(vsPrev.prev_date)}
            </Link>
          </p>
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Head count" value={formatSigned(vsPrev.head_count_delta, 0)} />
            <Stat label="Median" value={formatSigned(vsPrev.median_delta)} />
            <Stat label="Top score" value={formatSigned(vsPrev.top_score_delta, 0)} />
            <Stat label="Difficulty" value={formatSigned(vsPrev.difficulty_delta)} />
          </div>
        </div>
      )}
    </Card>
  );
}
