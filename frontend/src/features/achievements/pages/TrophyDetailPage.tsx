import { useParams } from 'react-router';
import { formatDate } from '../../../lib/format';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { TabularData } from '../../../components/charts/types';
import { useAchievement } from '../api';
import { cumulativeByDate, cumulativeLineOption } from '../chartOptions';
import { explainers } from '../explainers';
import { ShowAllButton, useShowAll } from '../components/ShowAll';
import { ShooterLink } from '../components/ShooterLink';
import { TrophyIcon } from '../components/TrophyIcon';
import { formatPct } from '../labels';

const HOLDER_COLUMNS: TabularData['columns'] = [
  { key: 'date', label: 'Date', type: 'date' },
  { key: 'holders', label: 'Holders', type: 'int' },
];

/** Keyed by code so the "Show all" state never carries over from one trophy to the next. */
export function TrophyDetailPage() {
  const { code = '' } = useParams();
  return <TrophyDetail key={code} code={code} />;
}

function TrophyDetail({ code }: { code: string }) {
  const { data, isPending, isError } = useAchievement(code);
  const list = useShowAll(data?.holders ?? []);
  if (isPending) return <p role="status">Loading trophy…</p>;
  if (isError) return <p role="alert">Could not load this trophy.</p>;
  const { trophy, holders } = data;
  const points = cumulativeByDate(holders.map((h) => h.first_date));
  return (
    <div className="flex flex-col gap-4 p-4">
      <header className="flex min-w-0 items-center gap-4">
        <TrophyIcon
          artKey={trophy.art_key}
          metal={trophy.metal}
          locked={trophy.holders === 0}
          size={96}
        />
        <div className="min-w-0">
          <h1 className="text-2xl font-bold">{trophy.name}</h1>
          {trophy.label === null ? null : <p className="text-lg">{trophy.label}</p>}
          <p className="text-text-muted">{trophy.description}</p>
          <p className="text-sm text-text-muted">
            {trophy.holders} {trophy.holders === 1 ? 'holder' : 'holders'} ·{' '}
            {formatPct(trophy.rarity_pct)} of shooters
          </p>
        </div>
      </header>
      <ChartFrame
        title="Holders over time"
        subtitle="Cumulative number of shooters holding this trophy"
        option={cumulativeLineOption(points, 'Holders')}
        columns={HOLDER_COLUMNS}
        rows={points.map((p) => ({ date: p.date, holders: p.total }))}
        csvName={`holders-${trophy.code.replace(':', '-')}`}
        ariaLabel="Line chart of holders over time"
        urlKey="holders"
        zoom="x"
        explainer={explainers.holders}
      />
      <section aria-labelledby="holders-heading" className="flex flex-col gap-2">
        <h2 id="holders-heading" className="text-lg font-medium">
          Holders
        </h2>
        {holders.length === 0 ? (
          <p className="text-text-muted">Nobody holds this trophy yet.</p>
        ) : (
          <ul aria-label="Holders" className="flex flex-col gap-1">
            {list.visible.map((h) => (
              <li
                key={h.shooter_id}
                className="flex min-h-11 flex-wrap items-center justify-between gap-x-3"
              >
                <ShooterLink shooterId={h.shooter_id} name={h.display_name} />
                {h.shooter_status === 'deceased' ? (
                  <span className="text-xs text-text-muted">In memoriam</span>
                ) : null}
                <span className="text-sm text-text-muted">
                  <time dateTime={h.first_date}>{formatDate(h.first_date)}</time>
                  {h.count > 1 ? ` · ×${h.count}` : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
        {list.hidden ? (
          <ShowAllButton count={holders.length} noun="holders" onClick={list.showAll} />
        ) : null}
      </section>
    </div>
  );
}
