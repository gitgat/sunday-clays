import type { ReactNode } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { TabularData } from '../../../components/charts/types';
import { formatDate } from '../../../lib/format';
import { enumCodec, useUrlState } from '../../../lib/useUrlState';
import { useAchievements } from '../api';
import { rarityBarOption } from '../chartOptions';
import { explainers } from '../explainers';
import { TrophyCard } from '../components/TrophyCard';
import { ShowAllButton, useShowAll } from '../components/ShowAll';
import { ShooterLink } from '../components/ShooterLink';
import { TrophyIcon } from '../components/TrophyIcon';
import type { Category } from '../labels';
import { CATEGORIES, CATEGORY_LABELS, formatCount, trophyTitle } from '../labels';
import { METAL_COLORS, ONE_OFF_COLOR } from '../metals';

type CategoryFilter = Category | 'all';

/** `?cat=<category>` (C10 URL state); absent or unknown = every category. */
const CATEGORY_FILTER = enumCodec<CategoryFilter>(['all', ...CATEGORIES]);

const RARITY_COLUMNS: TabularData['columns'] = [
  { key: 'trophy', label: 'Trophy', type: 'string' },
  { key: 'category', label: 'Category', type: 'string' },
  { key: 'holders', label: 'Holders', type: 'int' },
  { key: 'rarity_pct', label: 'Rarity %', type: 'number' },
];

function CategoryButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`min-h-11 rounded-[20px] border px-4 ${active ? 'border-accent bg-primary text-text' : 'border-outline-variant text-text-muted'}`}
    >
      {children}
    </button>
  );
}

export function TrophyRoomPage() {
  // Writing the default ('all') deletes `cat` from the URL (Plan 07 useUrlState).
  const [filter, setFilter] = useUrlState<CategoryFilter>('cat', CATEGORY_FILTER, 'all');
  const category = filter === 'all' ? null : filter;
  const { data, isPending, isError } = useAchievements();
  const recent = useShowAll(data?.recent ?? []);

  if (isPending) return <p role="status">Loading trophies…</p>;
  if (isError) return <p role="alert">Could not load the Trophy Room.</p>;
  const capped = data.recent_total > data.recent.length;

  const shown =
    category === null ? data.trophies : data.trophies.filter((t) => t.category === category);
  const rows: TabularData['rows'] = shown.map((t) => ({
    trophy: trophyTitle(t),
    category: CATEGORY_LABELS[t.category],
    holders: t.holders,
    rarity_pct: t.rarity_pct,
  }));
  const bars = shown.map((t) => ({
    label: trophyTitle(t),
    rarityPct: t.rarity_pct,
    color: t.metal === null ? ONE_OFF_COLOR : METAL_COLORS[t.metal],
  }));

  return (
    <div className="flex flex-col gap-4 p-4">
      <header>
        <h1 className="text-2xl font-bold">Trophy Room</h1>
        <p className="text-text-muted">
          {data.trophies.length} trophies · {data.n_shooters} shooters with at least one round
        </p>
      </header>
      <div role="group" aria-label="Filter by category" className="flex flex-wrap gap-2">
        <CategoryButton
          active={category === null}
          onClick={() => {
            setFilter('all');
          }}
        >
          All
        </CategoryButton>
        {CATEGORIES.map((c) => (
          <CategoryButton
            key={c}
            active={category === c}
            onClick={() => {
              setFilter(c);
            }}
          >
            {CATEGORY_LABELS[c]}
          </CategoryButton>
        ))}
      </div>
      <ChartFrame
        title="Rarity"
        subtitle="Share of shooters who hold each trophy"
        option={rarityBarOption(bars)}
        columns={RARITY_COLUMNS}
        rows={rows}
        csvName="trophy-rarity"
        ariaLabel="Bar chart of trophy rarity"
        urlKey="rarity"
        zoom="none"
        explainer={explainers.rarity}
        height={Math.max(320, bars.length * 26)}
      />
      <section aria-label="Trophies">
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((t) => (
            <li key={t.code}>
              <TrophyCard trophy={t} />
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="recent-unlocks" className="flex flex-col gap-2">
        <h2 id="recent-unlocks" className="text-lg font-medium">
          Recent unlocks
        </h2>
        {data.recent.length === 0 ? (
          <p className="text-text-muted">No trophies have been earned yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {recent.visible.map((a) => (
              <li
                key={`${a.shooter_id}-${a.code}-${a.event_date}`}
                className="flex min-h-11 flex-wrap items-center gap-x-3"
              >
                <TrophyIcon artKey={a.art_key} metal={a.metal} locked={false} size={32} />
                <span>
                  <ShooterLink shooterId={a.shooter_id} name={a.display_name} /> earned{' '}
                  {trophyTitle(a)} on{' '}
                  <time dateTime={a.event_date}>{formatDate(a.event_date)}</time>
                </span>
              </li>
            ))}
          </ul>
        )}
        {recent.hidden ? (
          <ShowAllButton
            count={data.recent.length}
            noun="unlocks"
            latest={capped}
            onClick={recent.showAll}
          />
        ) : null}
        {capped && !recent.hidden ? (
          <p className="text-sm text-text-muted">
            The latest {formatCount(data.recent.length)} of {formatCount(data.recent_total)} unlocks
            are listed.
          </p>
        ) : null}
      </section>
    </div>
  );
}
