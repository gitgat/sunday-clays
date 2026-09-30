import { useId, useState } from 'react';
import { Card } from '../../../components/ui/Card';
import { ExplainerPanel, ExplainerToggle } from '../../../components/ui/Explainer';
import { useOnThisDay, type OnThisDayItem } from '../api';
import { explainers } from '../explainers';
import { formatFullDay, joinNames } from '../format';
import { YirLink } from './YirLink';

function describe(item: OnThisDayItem): string {
  if (item.has_scores) {
    if (item.winners.length === 0)
      return `${item.n_shooters} shooters · top score ${item.top_score}`;
    const winners = joinNames(item.winners.map((w) => w.display_name));
    return `${item.n_shooters} shooters · won by ${winners} (${item.top_score})`;
  }
  return item.head_count === null
    ? 'No scores recorded'
    : `${item.head_count} shooters (attendance only)`;
}

/** Home widget: the Sundays closest to today 1, 2 and 3 years ago. */
export function OnThisDayCard() {
  const query = useOnThisDay();
  const panelId = useId();
  const [open, setOpen] = useState(false);
  return (
    <Card title="On this day" className="min-w-0">
      <div className="mb-2">
        <ExplainerToggle
          label="About this card"
          panelId={panelId}
          open={open}
          onToggle={() => setOpen((v) => !v)}
        />
      </div>
      {open && (
        <div className="mb-3">
          <ExplainerPanel id={panelId} explainer={explainers.onThisDay} />
        </div>
      )}
      {query.isPending ? (
        <p role="status">Loading…</p>
      ) : query.isError ? (
        <p role="alert">Could not load On this day.</p>
      ) : query.data.items.length === 0 ? (
        <p className="text-text-muted">No Sunday near this date in the last three years.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {query.data.items.map((item) => (
            <li key={item.years_ago} className="min-w-0">
              <YirLink to={`/events/${item.event_date}`}>
                {item.years_ago === 1 ? '1 year ago' : `${item.years_ago} years ago`} ·{' '}
                {formatFullDay(item.event_date)}
              </YirLink>
              <p className="break-words text-sm text-text-muted">{describe(item)}</p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
